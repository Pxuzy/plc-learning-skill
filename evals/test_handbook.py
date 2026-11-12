#!/usr/bin/env python3
"""契约测试：交付物是一份可读手册，而不是逐课测验或报告流水线。"""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CORE_REFERENCES = {
    "template-overview.md",
    "example-overview.md",
    "structure-mapping.md",
    "template-structure-map.md",
    "example-structure-map.md",
    "handbook-guide.md",
    "template-handbook.md",
    "template-handbook-index.md",
    "example-handbook.md",
    "omron-smc2-xml-workflow.md",
    "template-st-xml-framework.md",
    "template-mfb-xml.md",
    "template-index.md",
    "template-state-machine.md",
    "template-interface-instances.md",
    "example-fb.md",
    "code-reading.md",
    "comment-quality.md",
    "process-and-signal-flow.md",
    "workflow.md",
}


def read(*parts: str) -> str:
    return ROOT.joinpath(*parts).read_text(encoding="utf-8")


def test_skill_centers_on_handbook_deliverable():
    skill = read("SKILL.md")
    assert "手册" in skill
    assert "段间逻辑关系" in skill
    assert "工艺" in skill
    assert "事实回答给可核验直接答复" in skill
    from test_entry_routing import read_heading
    delivery = read_heading("SKILL.md", "## 核心流程")
    assert all(term in delivery for term in ("B", "局部参考", "references/workflow.md", "局部产物校验"))
    assert re.search(r"仅.*有工具.*实际.*产物校验", delivery)
    execution = read_heading("references/workflow.md", "### 局部产物校验")
    for term in ("固定骨架", "填正文", "CLI 校验", "局部修正", "整稿重验", "scripts/check_local_explanation.py", "--source"):
        assert term in execution, term
    assert "完整手册、教学重建和源码归档才按对应入口运行适用检查并交付 `.md` 文件" in skill
    assert "M6 导师" not in skill and "过关标准" not in skill


def test_skill_st_contract_kept():
    skill = read("SKILL.md")
    assert "总框架 → 大框架 → 小框架 → 逐段精讲" in skill
    assert "一个大框架未讲完整不得切换到下一个" in skill


def test_reference_set_is_lean_and_indexed():
    refs = {p.name for p in (ROOT / "references").glob("*.md")}
    assert CORE_REFERENCES <= refs, CORE_REFERENCES - refs
    skill = read("SKILL.md")
    assert "references/catalog.md" in skill
    catalog = read("references", "catalog.md")
    for name in refs:
        assert f"`references/{name}`" in catalog, name


def test_handbook_guide_defines_three_layers_and_plain_language_ban():
    guide = read("references", "handbook-guide.md")
    for kind in ("数据依赖", "顺序依赖", "状态/步序依赖", "互锁/许可", "异常传递"):
        assert kind in guide, kind
    assert "执行元件" in guide and "完成信号" in guide
    assert "三层结构" in guide and "1. 功能定位" in guide
    assert "不适用边界" in guide
    assert "不得用“然后执行下一段”代替" in guide


def test_module_teaching_order_is_consistent_across_guide_and_entrypoint():
    guide=read("references","handbook-guide.md")
    skill=read("SKILL.md")
    sequence="功能定位与执行条件 → 源码 → 代码块整体讲解 → 形象示例 → 程序交互与段间交接"
    assert sequence in guide and sequence in skill
    assert "关键变量" in guide and "关键变量" in skill
    assert "源码行级细节由有效行内注释承担" in skill
    assert "正文不设逐行讲解" in guide

def test_handbook_template_has_required_chapters():
    tpl = read("references", "template-handbook.md")
    for chapter in (
        "## 一、工程与边界",
        "## 二、执行框架",
        "## 三、工艺主线",
        "## 四、工位地图与段分类",
        "## 五、模块详解",
        "## 六、段间与工位间逻辑关系",
        "## 八、异常、报警与恢复",
        "## 九、未确认与证据",
        "## 十、理解检验与审查",
    ):
        assert chapter in tpl, chapter
    assert "文档类型：handbook" in tpl
    assert "<!-- src: 起-止；来源/对象：" in tpl
    assert "## 五、模块详解 🔍（FB/POU 按对象选择模块）" in tpl
    assert "#### 1. 功能定位与执行条件" in tpl and "#### 3. 代码块整体讲解" in tpl and "#### 4. 形象示例" in tpl
    assert "源码块覆盖清单" in tpl
    assert "设计依据" in tpl and "取舍与代价" in tpl


def test_handbook_template_requires_default_per_line_comment_guidance():
    tpl=read("references","template-handbook.md")
    instructions=tpl.split("#### 2. 源码",1)[1].split("#### 3. 代码块整体讲解",1)[0]
    for term in ("默认对每条非空源行（含条件续行与结构闭合行）在完整原行后追加","空白、纯注释与未闭合块注释内部行除外","低价值或重复注释仍判错","语义审查"):
        assert term in instructions,term
    assert "有理解价值的行内注释" not in instructions
    assert "**逐句看**" not in tpl
    assert "处理过程" in tpl and "状态变化" in tpl

def test_handbook_template_marks_process_table_as_fictional():
    tpl = read("references", "template-handbook.md")
    assert "## 三、工艺主线" in tpl and '<a id="ch4">' in tpl, "工艺主线或第四章锚点缺失，切片无意义"
    process = tpl.split("## 三、工艺主线", 1)[1].split('<a id="ch4">', 1)[0]
    assert "虚构示例" in process
    assert "未知" in process


def test_st_template_uses_generic_evidence_and_inline_comment_rules():
    template = read("references", "template-st-xml-framework.md")
    instructions = template.split("<!-- src:", 1)[1].split("**逐句看**", 1)[0]
    assert "来源/对象" in instructions
    assert "XML" in instructions and "文件路径" in instructions
    assert "`none`" in instructions and "限制" in instructions
    assert "每条非空行（含条件续行与结构闭合行）在完整原行后追加 // AI: 短句" in instructions
    assert "空白与纯注释行除外" in instructions
    assert "行内" in instructions
    assert "语义审查" in instructions
    assert "| 类型 | 原始变量/实例 | 作用 | 来源/去向 | 来源证据 | 证据等级 |" in template
    assert "| 来源 | 交互 | 目标 | 条件/参数 | 影响 | 来源证据 |" in template


def test_module_details_use_compact_numbered_outline():
    tpl=read("references","template-handbook.md")
    sample=read("references","example-block-handbook.md")
    titles=("#### 1. 功能定位与执行条件","#### 2. 源码","#### 3. 代码块整体讲解","#### 4. 形象示例","#### 5. 程序交互与段间交接")
    for title in titles:assert title in tpl and title in sample,title
    assert '<a id="m01"></a>' in tpl
    assert '### M01 <模块名>' in tpl
    assert tpl.index("关键变量")<tpl.index("### M01 <模块名>")
    assert sample.index("关键变量介绍")<sample.index("```st")
    assert "**逐句看**" not in tpl and "**逐句看**" not in sample

def test_handbook_template_tracks_user_supplied_module_structure():
    tpl=read("references","template-handbook.md")
    for expected in ("## 十、理解检验与审查","功能块定义","设计依据","初始状态","输入序列","代码块整体讲解","处理过程","关键逻辑","状态变化","形象示例","程序交互与段间交接"):
        assert expected in tpl,expected
    assert tpl.index("#### 3. 代码块整体讲解")<tpl.index("#### 4. 形象示例")<tpl.index("#### 5. 程序交互与段间交接")
    assert "五部分分级标题" in tpl

def test_multi_unit_index_template_exists():
    idx = read("references", "template-handbook-index.md")
    assert "跨单元逻辑关系" in idx
    assert "source_sha256" in idx and "未变" in idx


def test_template_registry_is_the_single_routing_and_version_source():
    index = read("references", "template-index.md")
    for expected in (
        "共享基底", "对象模板", "可组合专题", "HBK", "FB", "ST", "STATE", "INTERFACE",
        "资料不足", "版本策略", "唯一来源",
    ):
        assert expected in index, expected
    skill = read("SKILL.md")
    assert "references/template-index.md" in skill


def test_example_marks_project_data_as_illustrative():
    sample = read("references", "example-handbook.md")
    assert "仅为结构示范" in sample
    assert "NJ501" not in sample
    fb = read("references", "example-fb.md")
    assert "假想占位" in fb
    assert "NJ501" not in fb
    assert "fbExampleA" in fb


def test_cases_cover_handbook_delivery():
    cases = read("evals", "cases.md")
    for title in (
        "把整套程序写成一份手册", "段间逻辑关系缺失", "多程序单元拆册", "受保护的 FB/FC",
        "代码与源程序对不上", "模板路由与资料不足",
    ):
        assert title in cases, title
    case21 = cases.split("## Case 21", 1)[1].split("## Case 22", 1)[0]
    assert "块级说明之后可以补充类比" in case21
    assert "不适用边界" in case21
    assert "类比可省略" in read("SKILL.md")
    assert "类比可选" in read("references", "handbook-guide.md") or "可选类比" in read("references", "handbook-guide.md")


def test_workflow_tracks_progress_by_dependencies_and_evidence():
    workflow = read("references", "workflow.md")
    assert "不按日/周排课程" in workflow
    assert "已识别" in workflow and "已讲解" in workflow and "已理解" in workflow
    assert "不按固定工位数量排程" in workflow
    assert "复杂框架默认" in workflow
    assert "代表工位推演完整周期" in workflow
    assert "第二工位比较共性和差异" in workflow
    assert "完整手册仍须按资料覆盖全部可读部分" in workflow
    assert "未答或跳过记为未验证" in workflow


def test_timer_dual_trace_is_conditional_not_universal():
    checklist = read("references", "quality-checklist.md")
    assert "仅当所讲源码确实涉及定时器" in checklist
    assert "不是通用必检项" in checklist
    assert "200ms TON" in checklist


def test_maintenance_verification_points_to_four_named_commands():
    skill = read("SKILL.md")
    assert "references/workflow.md" in skill
    from test_entry_routing import read_heading
    maintenance = read_heading("SKILL.md", "### 维护入口与模板来源核对")
    assert all(term in maintenance for term in ("维护", "审计", "技能维护与成果保护", "技能维护回归"))
    verification = read_heading("references/workflow.md", "### 技能维护回归")
    for command in ("evals/run.py", "validate_skill.py", "validate_template_index.py", "git diff --check"):
        assert command in verification
        assert command not in skill
    assert "四条校验" in read_heading("references/workflow.md", "### 技能维护与成果保护")
    assert "上面两行" not in skill


def main():
    tests = [
        test_maintenance_verification_points_to_four_named_commands,
        test_skill_centers_on_handbook_deliverable,
        test_skill_st_contract_kept,
        test_reference_set_is_lean_and_indexed,
        test_handbook_guide_defines_three_layers_and_plain_language_ban,
        test_module_teaching_order_is_consistent_across_guide_and_entrypoint,
        test_handbook_template_has_required_chapters,
        test_handbook_template_requires_default_per_line_comment_guidance,
        test_handbook_template_marks_process_table_as_fictional,
        test_st_template_uses_generic_evidence_and_inline_comment_rules,
        test_module_details_use_compact_numbered_outline,
        test_handbook_template_tracks_user_supplied_module_structure,
        test_multi_unit_index_template_exists,
        test_template_registry_is_the_single_routing_and_version_source,
        test_example_marks_project_data_as_illustrative,
        test_cases_cover_handbook_delivery,
        test_workflow_tracks_progress_by_dependencies_and_evidence,
        test_timer_dual_trace_is_conditional_not_universal,
    ]
    failed = 0
    for test in tests:
        try:
            test()
        except Exception as exc:
            failed += 1
            print(f"FAIL {test.__name__}: {exc}")
        else:
            print(f"PASS {test.__name__}")
    print(f"{len(tests) - failed}/{len(tests)} passed")
    return int(failed > 0)


if __name__ == "__main__":
    raise SystemExit(main())
