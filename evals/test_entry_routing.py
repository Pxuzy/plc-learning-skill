#!/usr/bin/env python3
"""入口模式与输出规模契约：小问题先轻量回答，深度规则按路由加载。"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"


def selector() -> str:
    text = SKILL.read_text(encoding="utf-8")
    match = re.search(r"(?ms)^### [^\n]*模式[^\n]*规模[^\n]*\n(.*?)(?=^#{1,3} |\Z)", text)
    assert match, "SKILL.md 缺少靠前的模式/规模选择器"
    return match.group(1)


def mode_line(body: str, mode: str) -> str:
    match = re.search(rf"(?m)^- \*\*{mode}\.\*\*[^\n]*$", body)
    assert match, f"缺少模式 {mode}"
    return match.group()


def test_selector_has_five_modes_and_minimum_scope_default():
    body = selector()
    expected = {
        "A": ("事实", "条件", "变量", "短代码片段", "直接回答"),
        "B": ("局部代码", "五部分块级局部讲解模板"),
        "C": ("完整手册", "完整手册路线"),
        "D": ("从零", "教学重建路线"),
        "E": ("原样保存", "源码归档路线"),
    }
    for mode, phrases in expected.items():
        line = mode_line(body, mode)
        assert line, f"缺少模式 {mode}"
        for phrase in phrases:
            assert phrase in line, f"模式 {mode} 缺少可观察路由契约：{phrase}"
    assert "默认选择最小满足范围" in body
    assert "用户明确" in body
    assert "跨多个模块" in body


def test_local_template_is_bounded_and_keeps_safety_floor():
    local = (ROOT / "references/local-code-explanation.md").read_text(encoding="utf-8")
    for phrase in (
        "关键变量前置",
        "功能定位与执行条件",
        "源码",
        "代码块整体讲解",
        "形象示例",
        "程序交互与段间交接",
    ):
        assert phrase in local, phrase
    assert "代码围栏逐字保留可见源码" in local
    assert "原有注释" in local
    assert "一小段完整源码后紧邻整块因果说明" in local
    assert "不从名字补齐" in local
    assert "物理动作" in local
    assert "明确要求详细/逐行" in local
    assert "范围标签不等于片段行号" in local


def test_mode_b_preserves_source_without_added_teaching_comments():
    body = selector()
    local = (ROOT / "references/local-code-explanation.md").read_text(encoding="utf-8")
    assert "五部分块级局部讲解模板" in mode_line(body, "B")
    assert "用户明确要原样代码时才只给原码" in local
    assert "原有注释" in local
    assert "代码围栏逐字保留" in local


def test_local_emoji_palette_is_rich_but_semantic():
    local = (ROOT / "references/local-code-explanation.md").read_text(encoding="utf-8")
    for emoji in ("🧭", "🏭", "🧩", "📥", "📤", "⚙️", "🧪", "🔗", "⚠️", "💡", "✅"):
        assert emoji in local, emoji
    assert "按语义选择" in local
    assert "代码、变量名、表格字段" in local


def test_skill_has_no_line_by_line_analysis_table_contract():
    active_files = [
        ROOT / "SKILL.md",
        ROOT / "references" / "handbook-guide.md",
        ROOT / "references" / "workflow.md",
        ROOT / "references" / "local-code-explanation.md",
        ROOT / "references" / "one-page-prompt.md",
        ROOT / "references" / "code-reading.md",
        ROOT / "references" / "quality-checklist.md",
        ROOT / "evals" / "cases.md",
    ]
    forbidden = ("逐行解析表", "源码后逐行解析表", "line-by-line sidecar", "external_line_notes")
    hits = []
    for path in active_files:
        text = path.read_text(encoding="utf-8")
        for phrase in forbidden:
            if phrase in text:
                hits.append(f"{path.name}:{phrase}")
    assert not hits, hits
    skill = SKILL.read_text(encoding="utf-8")
    assert "五部分块级结构" in skill
    assert "逐行解析" not in skill


def test_local_five_parts_are_separate_numbered_headings():
    local = (ROOT / "references/local-code-explanation.md").read_text(encoding="utf-8")
    headings = re.findall(r"(?m)^#### ([1-5])\. ([^\n]+)", local)
    assert [number for number, _ in headings] == list("12345"), headings
    for (_, actual), expected in zip(headings, ("功能定位与执行条件", "源码", "代码块整体讲解", "形象示例", "程序交互与段间交接")):
        assert actual.startswith(expected), (actual, expected)
    first_heading = re.search(r"(?m)^#### 1\.", local)
    assert first_heading and local.index("关键变量") < first_heading.start()


def test_local_explanation_defaults_to_five_part_block_layout():
    body = selector()
    local = mode_line(body, "B")
    assert "references/local-code-explanation.md" in local, "模式 B 未接入局部讲解参考"
    assert "五部分块级局部讲解模板" in local


def test_local_reference_is_not_loaded_for_other_routes():
    body = selector()
    for mode in "ACDE":
        assert "local-code-explanation.md" not in mode_line(body, mode)


def test_local_explanation_does_not_route_to_teaching_rebuild():
    body = selector()
    local = mode_line(body, "B")
    assert "五部分块级局部讲解模板" in local
    assert "从零" not in local
    assert "教学重建" not in local


def test_deep_routes_keep_explicit_references_and_trigger_conditions():
    body = selector()
    deep = body[body.index(mode_line(body, "C")) :]
    assert "理解复杂框架" in deep and "完整手册路线" in deep
    assert "从零" in deep and "归档" in deep
    assert "references/handbook-guide.md" in SKILL.read_text(encoding="utf-8")
    assert "references/teaching-from-scratch.md" in SKILL.read_text(encoding="utf-8")
    assert "references/source-archive.md" in SKILL.read_text(encoding="utf-8")


def test_complex_framework_intent_starts_guided_handbook_route():
    body = selector()
    complex_route = mode_line(body, "C")
    assert "理解复杂框架" in complex_route
    assert "自动走系统学习" in complex_route
    assert "不要求用户说出" in complex_route
    assert "默认选择最小满足范围" in body
    workflow = (ROOT / "references/workflow.md").read_text(encoding="utf-8")
    for phrase in ("复杂框架默认", "全局地图并开始第一阶段", "代表工位", "全部可读源码覆盖", "学习文档"):
        assert phrase in workflow, phrase


def test_maintenance_rules_are_outside_normal_answer_priority():
    body = selector()
    assert "当前问题范围 > 学习意图与任务模式 > 对应深度规则 > 维护/验证规则" in body
    assert "catalog" in body and "Rule ID" in body and "SHA-256" in body and "Git 提交" in body
    assert "只在维护技能或明确要求审计/归档时加载" in body


def test_handbook_reference_is_loaded_only_for_deep_route():
    guide = (ROOT / "references" / "handbook-guide.md").read_text(encoding="utf-8")
    assert "仅在" in guide and "完整手册" in guide
    assert "A/B" in guide



def test_selector_boundaries_and_letter_noise():
    text = SKILL.read_text(encoding="utf-8")
    heading = "### 模式与规模选择器（先判，默认最小满足）"
    noise = "A/B 与 PLC 的 Markdown **粗体**只是正文，不是模式行。\n"
    text = text.replace(heading + "\n", heading + "\n" + noise, 1)
    with patch.object(Path, "read_text", return_value=text):
        body = selector()
        assert noise.strip() in body
        assert "## Quick Start" not in body
        test_selector_has_five_modes_and_minimum_scope_default()
        test_local_explanation_does_not_route_to_teaching_rebuild()
        test_deep_routes_keep_explicit_references_and_trigger_conditions()
        test_maintenance_rules_are_outside_normal_answer_priority()
    # 子标题属于选择器；同级、上级标题才结束它。
    fixture = heading + "\n正文 A/B PLC\n#### 子规则\n保留\n### 下一节\n不保留\n"
    with patch.object(Path, "read_text", return_value=fixture):
        assert selector().strip() == "正文 A/B PLC\n#### 子规则\n保留"


def test_selector_rejects_route_and_safety_mutations():
    text = SKILL.read_text(encoding="utf-8")
    mutations = [
        (next(line for line in text.splitlines() if line.startswith(f"- **{mode}.**")), "")
        for mode in "ABCDE"
    ]
    mutations += [
        ("五部分块级局部讲解模板", "从零教学重建模板"),
        ("先加载 `references/local-code-explanation.md`，", ""),
        ("只在维护技能或明确要求审计/归档时加载", "始终加载"),
        ("不编造地址和机械动作", "允许按名称猜地址和机械动作"),
    ]
    checks = (
        test_selector_has_five_modes_and_minimum_scope_default,
        test_local_explanation_defaults_to_five_part_block_layout,
        test_local_explanation_does_not_route_to_teaching_rebuild,
        test_deep_routes_keep_explicit_references_and_trigger_conditions,
        test_complex_framework_intent_starts_guided_handbook_route,
        test_maintenance_rules_are_outside_normal_answer_priority,
    )
    for old, new in mutations:
        assert old in text, old
        bad = text.replace(old, new, 1)
        assert bad != text
        with patch.object(Path, "read_text", return_value=bad):
            rejected = False
            for check in checks:
                try:
                    check()
                except AssertionError:
                    rejected = True
            assert rejected, f"未拒绝路由/安全变异：{old}"


def test_common_entry_cannot_downgrade_mode_b_template():
    text = SKILL.read_text(encoding="utf-8")
    body = selector()
    assert "A/B 未要求深讲时可用几个自然句" not in body
    assert "A 未要求深讲时可用几个自然句" in body
    assert "模式 B 的源码呈现与表情按其专用参考" in body
    assert "局部问题仍按范围讲" in text
    quick = text.split("## Quick Start", 1)[1].split("## 核心流程", 1)[0]
    row = next(line for line in quick.splitlines() if "只读懂一个局部代码块" in line)
    assert "五部分" in row and "轻量局部模板" not in row
    title_rule = next(line for line in text.splitlines() if line.startswith("- **PLC-TITLE-EMOJI"))
    assert "模式 B 按局部参考的语义表情方案" in title_rule
    catalog = (ROOT / "references/catalog.md").read_text(encoding="utf-8")
    scope = next(line for line in catalog.splitlines() if line.startswith("| PLC-COMMENT-VALUE |"))
    assert "完整手册/教学重建" in scope
    assert "局部 B 默认原码" in scope


def test_local_scope_does_not_reduce_requested_depth():
    text = SKILL.read_text(encoding='utf-8')
    body = selector()
    assert '范围与深度分别判定' in body
    assert '局部块级深讲' in mode_line(body, 'B')
    assert '只在对象/范围有歧义或用户要求先核对时暂停' in body
    assert '直接粘贴的片段按可见范围核对后直接讲解' in body


def read_heading(path: str, heading: str) -> str:
    text = (ROOT / path).read_text(encoding='utf-8')
    match = re.search(r'(?m)^' + re.escape(heading) + r'\s*$',text)
    assert match, f'有序读取入口不存在：{path} / {heading}'
    level = len(heading.split(' ')[0])
    end = re.search(rf'(?m)^#{{1,{level}}} ',text[match.end():])
    result=text[match.end():match.end()+end.start() if end else len(text)]
    assert result.strip(), '读取区段不得为空'
    return result


def test_mode_b_ordered_read_trace_and_deep_method_sections():
    line = mode_line(selector(),'B')
    paths = re.findall(r'`(references/[^`]+)`',line)
    expected = ['references/local-code-explanation.md',
                'references/code-reading.md',
                'references/teaching-from-scratch.md',
                'references/quality-checklist.md']
    assert paths == expected, f'B 读取顺序漂移：{paths}'
    assert '每小段按第一性原理推导' in line
    assert '源码深讲模式（读真实工程时加载）' in line
    # 普通仅首尾两份；深讲按真实标题读取中间方法，禁止空提取后凭记忆写。
    normal = [paths[0],paths[-1]]
    assert all('catalog' not in path and 'template-index' not in path for path in normal)
    method=read_heading('references/code-reading.md','## 每小段按第一性原理推导')
    source=read_heading('references/teaching-from-scratch.md','## 源码深讲模式（读真实工程时加载）')
    assert method and source
    assert '单因素' in method and '状态账本' in method
    quick=SKILL.read_text().split('## Quick Start',1)[1].split('| 用户意图',1)[0]
    assert 'C' in quick and '仅' in quick and 'B' in quick, '索引通用前言仍可能覆盖 B 有序路线'


def test_code_reading_local_boundaries_at_actual_conflict_sections():
    sections = ('## 短代码问答（A/B）',
                '## 每个小段的固定结构：关键变量前置与块级说明',
                '## 按理解价值写说明（注释只能追加）',
                '## 代码解读单元模板')
    for heading in sections:
        body=read_heading('references/code-reading.md',heading)
        assert 'local-code-explanation.md' in body and 'B' in body, heading
    short=read_heading('references/code-reading.md',sections[0])
    assert '仅 A' in short, '不套表格的短答不得继续用于 B'


def main() -> int:
    tests = [
        test_mode_b_ordered_read_trace_and_deep_method_sections,
        test_code_reading_local_boundaries_at_actual_conflict_sections,
        test_local_scope_does_not_reduce_requested_depth,
        test_common_entry_cannot_downgrade_mode_b_template,
        test_selector_has_five_modes_and_minimum_scope_default,
        test_local_template_is_bounded_and_keeps_safety_floor,
        test_mode_b_preserves_source_without_added_teaching_comments,
        test_local_emoji_palette_is_rich_but_semantic,
        test_skill_has_no_line_by_line_analysis_table_contract,
        test_local_five_parts_are_separate_numbered_headings,
        test_local_explanation_defaults_to_five_part_block_layout,
        test_local_reference_is_not_loaded_for_other_routes,
        test_local_explanation_does_not_route_to_teaching_rebuild,
        test_deep_routes_keep_explicit_references_and_trigger_conditions,
        test_complex_framework_intent_starts_guided_handbook_route,
        test_maintenance_rules_are_outside_normal_answer_priority,
        test_handbook_reference_is_loaded_only_for_deep_route,
        test_selector_boundaries_and_letter_noise,
        test_selector_rejects_route_and_safety_mutations,
    ]
    discovered = {name for name, value in globals().items() if name.startswith("test_") and callable(value)}
    assert {test.__name__ for test in tests} == discovered, "新增测试未全部接入 runner"
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
