#!/usr/bin/env python3
"""关键变量前置与块级正文：真实文档正反向回归，不模拟PLC运行。"""
from pathlib import Path
import sys, re, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from block_layout import check_block_layout
from check_local_explanation import check_text
from test_local_explanation_contract import VALID as LOCAL_VALID, SOURCE as LOCAL_SOURCE
VALID='''# 工位片段学习手册 📘

> 工程：假想工位
> 文档类型：handbook
> 深度：代码深度
> 讲解版式：块级

## 一、整体功能与关键变量 🧭

**控制目标**：请求满足普通许可时记住本次启动状态。

### 关键变量介绍

| 变量名称 | 类型／方向 | 实际含义 | 有效条件／取值 | 主要用途 |
|---|---|---|---|---|
| `xRequest` | BOOL／输入 | 本次启动请求 | TRUE表示请求存在 | 参与许可判断 |
| `xPermit` | BOOL／输入 | 普通运行许可 | TRUE表示满足普通前提 | 限定接收请求 |
| `xRun` | BOOL／状态 | 本段保存的启动状态 | 此片段只有TRUE写入 | 保持到其他复位路径 |

<a id="m01"></a>
### M01 启动状态建立

#### 1. 功能定位与执行条件

**功能定位**：承接请求与普通许可，建立后续流程可读取的启动记忆。

**代码职责**：只在两项输入同时成立时写入启动状态。

**设计依据**：请求是当前输入，不足以证明后续仍在运行，因此另用状态保存结果；复位不在本片段中。

| 进入条件 | 必要原因 | 不满足时的行为 |
|---|---|---|
| `xRequest AND xPermit` | 请求与普通许可必须同时满足 | 跳过赋值并保留状态 |

#### 2. 源码

<!-- src: none；来源/对象：本测试虚构片段，非现场源码 -->
```st
IF xRequest AND xPermit THEN // 当前请求必须同时满足普通许可才接收
    xRun := TRUE; // 留下启动记忆；输入随后撤销不构成本段复位
END_IF;
```

#### 3. 代码块整体讲解

**处理过程**：两项输入同时有效才建立启动状态，条件不成立时不更新它。

**关键逻辑**：输入资格与跨扫描记忆分离，避免把没有新请求误读为停止。

**写法好处**：请求只在条件成立时置位、只在第5段复位，同一变量只有两处写，排查时无需全程序搜索；阀另用自保持，不随请求抖动。

**状态变化**：本段只写TRUE，没有FALSE路径；清除需要查其他写入点。

#### 4. 形象示例

**场景设定**：按钮请求建立状态后松开，观察是否仍然保持。

**初始状态**：假设 `xRun = FALSE`，本实例周期执行，无其他写入。

| 阶段／扫描 | 输入与原状态 | 本段处理 | 执行结果 |
|---|---|---|---|
| 第1次扫描 | Request与Permit都TRUE | 进入赋值 | Run变TRUE |
| 第2次扫描 | Request变FALSE | 跳过赋值 | Run保持TRUE |
| 第3次扫描 | Request仍FALSE、Permit为TRUE | 再次跳过赋值 | Run仍TRUE |

**理解要点**：条件失效只是不写新值，不等于状态自动复位。

#### 5. 程序交互与段间交接

| 关系 | 来源 | 目标 | 关联变量 | 实际作用 |
|---|---|---|---|---|
| 输出 | 本段 | 下游消费程序未提供 | `xRun` | 提供启动记忆，实际消费时机未知 |

**交接要点**：不能由本片段确认何时清除、其他写方或下游接单协议。
'''

def run(text):
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/'book.md';p.write_text(text)
        return subprocess.run([sys.executable,'-B',str(ROOT/'scripts/validate_handbook.py'),str(p)],capture_output=True,text=True)

class BlockLayoutTests(unittest.TestCase):
    def test_real_block_document_without_duplicate_line_section_passes(self):
        r=run(VALID);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
    def test_missing_overall_explanation_is_rejected(self):
        bad=VALID.replace('**处理过程**：两项输入同时有效才建立启动状态，条件不成立时不更新它。','**处理过程**：')
        self.assertNotEqual(bad,VALID);r=run(bad)
        self.assertNotEqual(r.returncode,0,r.stdout);self.assertIn('处理过程',r.stdout)
    def test_missing_variables_or_late_variables_is_rejected(self):
        a=VALID.index('### 关键变量介绍');b=VALID.index('<a id="m01">')
        table=VALID[a:b]
        for text in (VALID[:a]+VALID[b:],VALID[:a]+VALID[b:]+'\n'+table):
            with self.subTest():
                r=run(text);self.assertNotEqual(r.returncode,0,r.stdout);self.assertIn('关键变量',r.stdout)

    def test_local_variable_table_must_precede_module_heading(self):
        self.assertEqual(check_text(LOCAL_VALID,LOCAL_SOURCE)['errors'],[])
        a=LOCAL_VALID.index('| 变量 |');b=LOCAL_VALID.index('\n\n<a id="m01">',a)
        table=LOCAL_VALID[a:b]
        moved=LOCAL_VALID[:a]+LOCAL_VALID[b:]
        marker='#### 1. 功能定位与执行条件 🎯'
        moved=moved.replace(marker,marker+'\n\n'+table,1)
        errors='\n'.join(check_block_layout(moved,mode='local'))
        self.assertIn('关键变量表',errors)
        self.assertIn('模块标题之前',errors)

    def test_local_one_line_summary_and_source_location_have_fixed_sections(self):
        self.assertEqual(check_text(LOCAL_VALID,LOCAL_SOURCE)['errors'],[])
        for label in ('一句话说清','来源定位'):
            original=re.search(rf'(?m)^\*\*{label}\*\*：[^\n]+\n\n',LOCAL_VALID)[0]
            moved=LOCAL_VALID.replace(original,'',1).replace('<!-- 本段已完 -->',original+'<!-- 本段已完 -->',1)
            errors=check_text(moved,LOCAL_SOURCE)['errors']
            self.assertTrue(errors)
            self.assertTrue(all(label in item for item in errors),errors)

    def test_nested_examples_cannot_supply_local_fields_or_variables(self):
        for label in ('一句话说清','来源定位'):
            original=re.search(rf'(?m)^\*\*{label}\*\*：[^\n]+',LOCAL_VALID)[0]
            for replacement in ('> '+original,'- '+original,'```text\n'+original+'\n```'):
                errors=check_text(LOCAL_VALID.replace(original,replacement,1),LOCAL_SOURCE)['errors']
                self.assertTrue(any(label in item for item in errors),errors)
        a=LOCAL_VALID.index('| 变量 |');b=LOCAL_VALID.index('\n\n<a id="m01">',a)
        table=LOCAL_VALID[a:b]
        for replacement in ('\n'.join('> '+line for line in table.splitlines()),'```text\n'+table+'\n```'):
            errors=check_block_layout(LOCAL_VALID[:a]+replacement+LOCAL_VALID[b:],mode='local')
            self.assertTrue(any('关键变量' in item for item in errors),errors)

    def test_handbook_keeps_its_source_before_variables_boundary(self):
        a=VALID.index('| 变量名称 |');b=VALID.index('\n\n<a id="m01">',a)
        table=VALID[a:b]
        moved=(VALID[:a]+VALID[b:]).replace('#### 1. 功能定位与执行条件',
                    '#### 1. 功能定位与执行条件\n\n'+table,1)
        self.assertEqual(check_block_layout(moved,mode='handbook'),[])
    def test_reintroducing_duplicate_line_explanation_is_rejected(self):
        bad=VALID.replace('#### 3. 代码块整体讲解','#### 3. 逐行讲解')
        r=run(bad);self.assertNotEqual(r.returncode,0,r.stdout);self.assertIn('整体讲解',r.stdout)
    def test_missing_example_or_interaction_and_wrong_order_are_rejected(self):
        for old,new in [('#### 4. 形象示例','#### 4. 可省略'),('#### 5. 程序交互与段间交接','#### 5. 不适用'),('#### 2. 源码','#### 4. 形象示例')]:
            with self.subTest(old=old):
                bad=VALID.replace(old,new);self.assertNotEqual(bad,VALID)
                r=run(bad);self.assertNotEqual(r.returncode,0,r.stdout)
    def test_missing_inline_comment_is_still_rejected(self):
        bad=VALID.replace(' // 留下启动记忆；输入随后撤销不构成本段复位','')
        r=run(bad);self.assertNotEqual(r.returncode,0,r.stdout);self.assertIn('缺少有效行内注释',r.stdout)
    def test_canonical_template_and_entry_default_to_block_level(self):
        t=(ROOT/'references/template-handbook.md').read_text()
        self.assertIn('#### 3. 代码块整体讲解',t)
        self.assertNotIn('**逐句看**',t)
        self.assertLess(t.index('关键变量'),t.index('```text\n<教学注释版'))
        self.assertIn('讲解版式：块级',(ROOT/'SKILL.md').read_text())
    def test_multistation_nested_module_uses_same_contract(self):
        text=VALID.replace('<a id="m01"></a>\n### M01 启动状态建立','### 模块跳转\n\n[M01](#m01)\n\n<a id="w01"></a>\n### W01 教学工位\n\n<a id="m01"></a>\n#### M01 启动状态建立')
        text=re.sub(r'(?m)^#### ([1-5]\. )',r'##### \1',text)
        r=run(text);self.assertEqual(r.returncode,0,r.stdout+r.stderr)

    def test_handbook_mode_accepts_b0_b1_without_changing_local_ids(self):
        for identifier in ('B0','B1'):
            handbook=VALID.replace('M01',identifier)
            self.assertEqual(check_block_layout(handbook,mode='handbook'),[])
            self.assertEqual(run(handbook).returncode,0)
            self.assertTrue(check_block_layout(LOCAL_VALID.replace('M01',identifier),mode='local'))
    def test_legacy_source_before_intro_cannot_count_as_valid_block(self):
        a=VALID.index('<!-- src:');b=VALID.index('#### 3. 代码块整体讲解')
        code=VALID[a:b]
        bad=VALID[:a]+VALID[b:]
        bad=bad.replace('#### 1. 功能定位与执行条件',code+'\n#### 1. 功能定位与执行条件')
        r=run(bad);self.assertNotEqual(r.returncode,0,r.stdout)
        self.assertIn('源码小节',r.stdout)
    def test_missing_each_overall_field_is_rejected(self):
        for label in ('处理过程','关键逻辑','状态变化'):
            bad=re.sub(rf'(?m)^(\*\*{label}\*\*：).*$',r'\1',VALID)
            with self.subTest(label=label):
                r=run(bad);self.assertNotEqual(r.returncode,0,r.stdout);self.assertIn(label,r.stdout)
    def test_vague_explanation_is_rejected_not_just_missing(self):
        """空话必须被拒：写在规范里不够，生成即失败才算数。"""
        cases={
            '处理过程':'执行判断，满足条件则赋值。',
            '关键逻辑':'条件很重要。',
            '状态变化':'变量变化了。',
            '设计依据':'根据控制目标需要这些条件。',
        }
        for label,text in cases.items():
            bad=re.sub(rf'(?m)^(\*\*{label}\*\*：).*$',lambda m:m[1]+text,VALID)
            with self.subTest(label=label):
                self.assertNotEqual(bad,VALID)
                r=run(bad);self.assertNotEqual(r.returncode,0,r.stdout)
                self.assertRegex(r.stdout,rf'{label}.*(空话|过短)')
    def test_multiline_field_content_is_accepted(self):
        """字段内容写在下一行的列表里是正常写法，不能误判为空。"""
        good=VALID.replace(
            '**处理过程**：两项输入同时有效才建立启动状态，条件不成立时不更新它。',
            '**处理过程**：\n\n每扫描读入两项输入：\n- 请求与许可同时成立时建立启动状态\n- 任一失效时跳过赋值并保留原值')
        self.assertNotEqual(good,VALID)
        r=run(good);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
    def test_oversized_single_block_is_rejected(self):
        """一次贴一大段再集中解释，必须被拒。"""
        big='\n'.join([f'    xStep{n} := TRUE; // 第{n}步置位并保持到下一步' for n in range(30)])
        code=f'```st\nIF xEnable THEN\n{big}\nEND_IF;\n```'
        bad=VALID.replace('```st\nIF xRequest AND xPermit THEN // 当前请求必须同时满足普通许可才接收\n    xRun := TRUE; // 留下启动记忆；输入随后撤销不构成本段复位\nEND_IF;\n```',code)
        self.assertNotEqual(bad,VALID)
        r=run(bad)
        self.assertNotEqual(r.returncode,0,r.stdout)
        self.assertIn('超过',r.stdout)
    def test_segmented_small_blocks_are_accepted(self):
        """按逻辑切成小段、每段后紧邻讲解，应当通过。"""
        good=VALID.replace(
            '```st\nIF xRequest AND xPermit THEN // 当前请求必须同时满足普通许可才接收\n    xRun := TRUE; // 留下启动记忆；输入随后撤销不构成本段复位\nEND_IF;\n```',
            '```st\nIF xRequest AND xPermit THEN // 当前请求必须同时满足普通许可才接收\n    xRun := TRUE; // 留下启动记忆；输入随后撤销不构成本段复位\nEND_IF;\n```\n\n先看判断与赋值这一段，再看下一段。')
        self.assertNotEqual(good,VALID)
        r=run(good);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
    def test_pure_description_without_reasoning_is_rejected(self):
        """筛出明显缺少因果线索的字段，不声称自动判定推导正确。"""
        cases={
            '设计依据':'输入有三个条件，代码按顺序判断后执行对应动作。',
            '关键逻辑':'每扫描读入两项输入，按AND规则判断，满足时进入分支赋值。',
        }
        for label,text in cases.items():
            bad=re.sub(rf'(?m)^(\*\*{label}\*\*：).*$',lambda m:m[1]+text,VALID)
            with self.subTest(label=label):
                self.assertNotEqual(bad,VALID)
                r=run(bad);self.assertNotEqual(r.returncode,0,r.stdout)
                self.assertIn('没有推导',r.stdout)
    def test_reasoning_with_causal_link_is_accepted(self):
        good=VALID.replace(
            '**设计依据**：请求是当前输入，不足以证明后续仍在运行，因此另用状态保存结果；复位不在本片段中。',
            '**设计依据**：请求是当前输入，不足以证明后续仍在运行；若直接跟随输入，抖动会让状态丢失，因此另用状态保存结果。')
        self.assertNotEqual(good,VALID)
        r=run(good);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
    def test_bare_placeholder_is_rejected_but_specific_unknown_passes(self):
        for label, placeholder in (('关键逻辑','未知。'), ('状态变化','无。'), ('写法好处','待补。')):
            with self.subTest(label=label):
                bad=re.sub(rf'(?m)^(\*\*{label}\*\*：).*$', lambda m:m[1]+placeholder, VALID)
                r=run(bad)
                self.assertNotEqual(r.returncode,0,r.stdout+r.stderr)
                self.assertIn('占位',r.stdout)
        good=re.sub(r'(?m)^(\*\*写法好处\*\*：).*$',
                    lambda m:m[1]+'比较优势未知：本片段没有其他写方或调用证据。', VALID)
        r=run(good);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
    def test_process_preface_before_document_is_rejected(self):
        for preface in ('我会按规范讲解。', '根据你刚才的修改意见，以下是新稿。'):
            with self.subTest(preface=preface):
                bad=preface+VALID
                r=run(bad)
                self.assertNotEqual(r.returncode,0,r.stdout+r.stderr)
                self.assertIn('正式稿',r.stdout)

    def test_short_evidence_and_unknown_are_valid_not_forced_to_pad(self):
        for label, text in (
            ('写法好处', '比较优势未知。'),
            ('状态变化', '本次不写。'),
            ('设计依据', '必要性未知。'),
            ('关键逻辑', '否则丢值。'),
        ):
            good=re.sub(rf'(?m)^(\*\*{label}\*\*：).*$', lambda m:m[1]+text, VALID)
            with self.subTest(label=label):
                self.assertNotEqual(good, VALID)
                r=run(good); self.assertEqual(r.returncode, 0, r.stdout+r.stderr)
    def test_missing_benefit_field_is_rejected(self):
        """只讲逻辑不讲「这样写好在哪」，判定讲解不完整。"""
        bad=re.sub(r'(?m)^\*\*写法好处\*\*：.*$\n?','',VALID)
        self.assertNotEqual(bad,VALID)
        r=run(bad);self.assertNotEqual(r.returncode,0,r.stdout)
        self.assertIn('写法好处',r.stdout)
    def test_benefit_field_cannot_be_a_bare_claim(self):
        bad=re.sub(r'(?m)^\*\*写法好处\*\*：.*$','**写法好处**：这样写更好。',VALID)
        r=run(bad);self.assertNotEqual(r.returncode,0,r.stdout)
        self.assertIn('写法好处',r.stdout)
    def test_current_sample_uses_canonical_structure(self):
        p=ROOT/'references/example-block-handbook.md'
        self.assertTrue(p.is_file(),'缺少块级正文示例')
        if p.exists():
            r=run(p.read_text());self.assertEqual(r.returncode,0,r.stdout+r.stderr)

# ---- 长闭合结构：完整保留一次 + 分支导航，与“一次一大段”区分 ----
_ORIG_BLOCK = ('```st\nIF xRequest AND xPermit THEN // 当前请求必须同时满足普通许可才接收\n'
               '    xRun := TRUE; // 留下启动记忆；输入随后撤销不构成本段复位\nEND_IF;\n```')

_SINGLE_STRUCT = '\n'.join(
    ['IF xEnable THEN // 总使能成立才进入本结构；为假时整块跳过']
    + [f'    IF xStep{n} THEN // 第{n}步条件成立才进入该分支' + chr(10)
       + f'        xMark{n} := TRUE; // 记录第{n}步完成，供后续分支读取'
       + chr(10) + '    END_IF; // 关闭第' + str(n) + '步分支'
       for n in range(1, 13)]
    + ['END_IF; // 关闭总使能结构'])

LONG_SINGLE = VALID.replace(_ORIG_BLOCK, '```st\n' + _SINGLE_STRUCT + '\n```')
LONG_WITH_NAV = LONG_SINGLE.replace(
    '#### 3. 代码块整体讲解',
    '分支导航：[第1–6步](#branch-1)、[第7–12步](#branch-2)\n\n'
    '<a id="branch-1"></a>\n\n<a id="branch-2"></a>\n\n#### 3. 代码块整体讲解')


class LongStructureTests(unittest.TestCase):
    def test_single_closed_structure_over_limit_with_branch_navigation_passes(self):
        """长 IF/CASE 保留完整源码一次、按分支锚点讲解，不应被判成一次一大段。"""
        self.assertNotEqual(LONG_WITH_NAV, LONG_SINGLE)
        r = run(LONG_WITH_NAV)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_single_closed_structure_over_limit_without_navigation_is_rejected(self):
        """同样是长结构，但没有分支导航就等于贴完不拆，仍须被拒。"""
        r = run(LONG_SINGLE)
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn('超过', r.stdout)

    def test_unrelated_anchors_do_not_satisfy_branch_navigation(self):
        unrelated = LONG_SINGLE.replace(
            '#### 3. 代码块整体讲解',
            '导航：[目录](#toc)、[模块](#module)\n\n'
            '<a id="toc"></a>\n\n<a id="module"></a>\n\n#### 3. 代码块整体讲解')
        r = run(unrelated)
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn('超过', r.stdout)

    def test_many_statements_over_limit_still_rejected(self):
        """多语句堆叠不是单一闭合结构，拆块要求不放宽。"""
        r = run(VALID.replace(_ORIG_BLOCK, '```st\nIF xEnable THEN\n'
                              + '\n'.join([f'    xStep{n} := TRUE; // 第{n}步置位并保持到下一步' for n in range(30)])
                              + '\nEND_IF;\n```'))
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn('超过', r.stdout)


if __name__=='__main__':unittest.main(verbosity=2)
