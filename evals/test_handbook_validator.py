#!/usr/bin/env python3
"""手册校验器的正反向回归。"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_handbook.py"
SAMPLE = ROOT / "references" / "example-handbook.md"
FB_SAMPLE = ROOT / "references" / "example-fb.md"


def _historical_sample_text():
    """Keep mutation anchors for historical per-unit tests, without changing the runtime sample.

    Default annotation compliance of the shipped sample has its own regression.
    """
    return re.sub(r" // AI: [^\n]*", "", SAMPLE.read_text(encoding="utf-8"))


def run(doc: Path, *extra: str, default: bool = False):
    """本文件复核历史 HBK@2.2 样例：默认走 --legacy-selective，保留 per-unit
    覆盖/质量/语义审查断言；default=True 才用已确认的逐行注释新默认。"""
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPT), str(doc), *extra] + ([] if default else ["--legacy-selective"]),
        capture_output=True, text=True, cwd=ROOT, check=False,
    )


def test_each_module_anchor_is_unique_and_linkable():
    doc = _variant((
        '<a id="m02"></a>', '<a id="x02"></a>',
    ))
    result = run(doc)
    assert result.returncode == 1
    assert "交叉引用失效：# m02" in result.stdout


def test_module_heading_must_not_link_to_itself():
    doc = _variant(("#### M02 夹紧控制", "#### [M02](#m02) 夹紧控制"))
    result = run(doc)
    assert result.returncode == 1
    assert "模块标题不应把编号链接到自身锚点" in result.stdout


def test_module_heading_without_jump_entry_fails():
    doc = _variant(("| [M02 夹紧控制](#m02) | 步序 20 夹紧、到位推进 |", "| M02 夹紧控制 | 步序 20 夹紧、到位推进 |"))
    result = run(doc)
    assert result.returncode == 1
    assert "未加入目录或模块跳转表" in result.stdout


def test_chapter_without_matching_anchor_fails():
    doc = _variant(('<a id="ch1"></a>', '<a id="wrong"></a>'))
    result = run(doc)
    assert result.returncode == 1
    assert "章节标题缺少匹配锚点：ch1" in result.stdout


def test_analogy_is_optional():
    text = _historical_sample_text()
    analogy_pos = text.index("**形象理解**")
    analogy_end = text.index("\n**变量怎么变**", analogy_pos)
    text = text[:analogy_pos] + text[analogy_end + 1:]
    doc = Path(tempfile.mkdtemp()) / "no-analogy.md"
    doc.write_text(text, encoding="utf-8")
    result = run(doc)
    assert result.returncode == 0, result.stdout + result.stderr


def test_analogy_must_follow_line_by_line_explanation():
    text = _historical_sample_text()
    block_start = text.index("<a id=\"m02\"></a>")
    analogy_pos = text.index("**形象理解**", block_start)
    analogy_end = text.index("\n**变量怎么变**", analogy_pos)
    analogy_block = text[analogy_pos:analogy_end].strip()
    text = text[:analogy_pos] + text[analogy_end:]
    line_pos = text.index("**逐句看**", block_start)
    text = text[:line_pos] + analogy_block + "\n\n" + text[line_pos:]
    doc = Path(tempfile.mkdtemp()) / "h.md"
    doc.write_text(text, encoding="utf-8")
    assert text.index("**形象理解**", block_start) < text.index("**逐句看**", block_start)
    result = run(doc)
    assert result.returncode == 1
    assert "必须放在逐句说明之后" in result.stdout


def test_sample_handbook_passes():
    # 该样例是历史 HBK@2.2 选择性注释夹具：复核其 per-unit 覆盖/质量，
    # 新默认的逐行尾注门禁由 test_default_annotations 单独覆盖。
    result = run(SAMPLE)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "0 个错误" in result.stdout


def test_fb_topic_sample_passes():
    result = run(FB_SAMPLE)
    assert result.returncode == 0, result.stdout + result.stderr


def test_pure_signal_flow_document_does_not_need_handbook_chapters():
    text = """# 信号链专题

> 文档类型：handbook | 深度：流程深度
> 模板组合：HBK@2.2 + FLOW@2.2

## 目录
- [信号链](#signal)
- [证据边界](#evidence)

<a id="signal"></a>
## 信号链

| 跳 | 变量 | 作用 | 证据 |
|---|---|---|---|
| 1 | `xRequest` | 请求信号 | 可见源码 |

<a id="evidence"></a>
## 证据边界

仅说明当前可见信号，不推断机械动作。
"""
    doc = Path(tempfile.mkdtemp()) / "signal.md"
    doc.write_text(text, encoding="utf-8")
    result = run(doc)
    assert result.returncode == 0, result.stdout + result.stderr


def test_registered_template_composition_is_accepted():
    text = """# FB interface note

> 文档类型：handbook | 深度：流程深度
> 模板组合：HBK@2.2 + FB@2.2 + INTERFACE@2.1

## Definition
Only visible interface facts are recorded.
"""
    doc = Path(tempfile.mkdtemp()) / "fb.md"
    doc.write_text(text, encoding="utf-8")
    result = run(doc)
    assert result.returncode == 0, result.stdout + result.stderr


def test_unknown_template_id_fails():
    text = """# Note

> 文档类型：handbook | 深度：流程深度
> 模板组合：HBK@2.2 + FB-UNKNOWN@1.0

## Object
<details>
"""
    doc = Path(tempfile.mkdtemp()) / "unknown.md"
    doc.write_text(text, encoding="utf-8")
    result = run(doc)
    assert result.returncode == 1
    assert "模板组合包含未知 ID" in result.stdout


def test_unregistered_template_combination_fails():
    text = """# Overview

> 文档类型：handbook | 深度：结构深度
> 模板组合：OVR@1.0 + FB@2.2

## Summary
<summary>
"""
    doc = Path(tempfile.mkdtemp()) / "combo.md"
    doc.write_text(text, encoding="utf-8")
    result = run(doc)
    assert result.returncode == 1
    assert "模板组合不兼容" in result.stdout


def test_included_alarm_matrix_still_requires_its_fields():
    text = """# 报警专题

> 文档类型：handbook | 深度：流程深度
## 目录
- [异常与恢复](#alarms)
<a id="alarms"></a>
## 异常与恢复

| 报警 | 条件 | 处理 |
|---|---|---|
| AL-01 | 条件成立 | 停止 |
"""
    doc = Path(tempfile.mkdtemp()) / "alarms.md"
    doc.write_text(text, encoding="utf-8")
    result = run(doc)
    assert result.returncode == 1
    assert "报警矩阵缺少" in result.stdout


def test_unsafe_force_io_or_safety_bypass_recommendation_fails():
    doc = _variant((
        "审查：模块锚点与跳转已校验；源码范围与示例为脱敏示意，不能替代真实工程对账。",
        "建议强制 I/O 排查故障，并临时旁路安全互锁。",
    ))
    result = run(doc)
    assert result.returncode == 1
    assert "只读安全边界" in result.stdout


def test_positive_unsafe_recommendations_fail():
    for sentence in ("建议修改 PLC 程序。", "请旁通安全回路。", "请通过设备试运行验证差异。"):
        doc = _variant((
            "审查：模块锚点与跳转已校验；源码范围与示例为脱敏示意，不能替代真实工程对账。",
            sentence,
        ))
        result = run(doc)
        assert result.returncode == 1, sentence
        assert "只读安全边界" in result.stdout, sentence


def test_read_only_safety_boundary_is_allowed():
    text = """# Safety boundary

> 文档类型：handbook | 深度：流程深度
> 模板组合：HBK@2.2 + FLOW@2.2

## Scope
禁止修改 PLC 程序；不下载、不强制 I/O、不旁路安全、不做产线试错。
"""
    doc = Path(tempfile.mkdtemp()) / "safe.md"
    doc.write_text(text, encoding="utf-8")
    result = run(doc)
    assert result.returncode == 0, result.stdout + result.stderr


def test_negated_safety_list_is_allowed():
    text = """# Safety boundary

> 文档类型：handbook | 深度：流程深度
> 模板组合：HBK@2.2 + INTERFACE@2.1

## Scope
不得通过在线改参、强制 I/O 或设备试运行验证差异。
"""
    doc = Path(tempfile.mkdtemp()) / "safe-list.md"
    doc.write_text(text, encoding="utf-8")
    result = run(doc)
    assert result.returncode == 0, result.stdout + result.stderr


def test_missing_chapter_fails():
    text = _historical_sample_text()
    text = text.replace("## 六、段间与工位间逻辑关系", "## 六、删掉的章节", 1)
    with tempfile.TemporaryDirectory() as td:
        doc = Path(td) / "h.md"
        doc.write_text(text, encoding="utf-8")
        result = run(doc)
    assert result.returncode == 1
    assert "缺少章节：## 六、段间与工位间逻辑关系" in result.stdout


def test_chapter_outside_declared_scope_fails():
    text = _historical_sample_text()
    text = text.replace(
        "> 适用章节：ch1, ch2, ch3, ch4, ch5, ch6, ch7, ch8, ch9, ch10",
        "> 适用章节：ch1", 1,
    )
    with tempfile.TemporaryDirectory() as td:
        doc = Path(td) / "scope.md"
        doc.write_text(text, encoding="utf-8")
        result = run(doc, "--final")
    assert result.returncode == 1
    assert "超出适用章节范围" in result.stdout


def test_chapters_must_follow_declared_order_but_may_skip():
    text = _historical_sample_text()
    text = text.replace(
        "> 适用章节：ch1, ch2, ch3, ch4, ch5, ch6, ch7, ch8, ch9, ch10",
        "> 适用章节：ch1, ch3, ch5", 1,
    )
    keep = {"ch1", "ch3", "ch5"}
    chunks = re.split(r"(?m)(?=^<a id=\"ch\d+\"></a>$)", text)
    text = "".join(chunk for chunk in chunks if not (m := re.search(r'<a id="(ch\d+)"></a>', chunk)) or m.group(1) in keep)
    text = re.sub(r"\(#ch(?:2|4|6|7|8|9|10)\)", "", text)
    doc = Path(tempfile.mkdtemp()) / "ordered-subset.md"
    doc.write_text(text, encoding="utf-8")
    assert run(doc).returncode == 0
    reversed_text = text.replace("## 一、工程与边界", "## TEMP、工程与边界", 1)
    reversed_text = reversed_text.replace("## 三、工艺主线", "## 一、工艺主线", 1)
    reversed_text = reversed_text.replace("## TEMP、工程与边界", "## 三、工程与边界", 1)
    doc.write_text(reversed_text, encoding="utf-8")
    result = run(doc)
    assert result.returncode == 1
    assert "章节顺序错误" in result.stdout


def test_every_module_has_four_plain_bold_subheadings():
    text = _historical_sample_text()
    expected = (
        "**1. 功能定位**",
        "**2. 推演示例**",
        "**3. 实现与逐句说明**",
        "**4. 与其他程序的交互**",
    )
    assert all(text.count(title) > 0 for title in expected)
    assert not re.search(r"(?m)^#{1,6} [1-4]\. (?:功能定位|推演示例|实现与逐句说明|与其他程序的交互)", text)


def test_readable_code_requires_worked_example_before_plc_source():
    text = _historical_sample_text()
    start = text.index("| 场景 | 初始状态", text.index('<a id="m02"></a>'))
    end = text.index("**3. 实现与逐句说明**", start)
    example = text[start:end]
    text = text[:start] + text[end:]
    code_end = text.index("```", text.index("```pascal", text.index('<a id="m02"></a>')) + 3) + 3
    text = text[:code_end] + "\n\n" + example + text[code_end:]
    doc = Path(tempfile.mkdtemp()) / "example-after-code.md"
    doc.write_text(text, encoding="utf-8")
    result = run(doc)
    assert result.returncode == 1
    assert "示例必须位于 PLC 源码之前" in result.stdout, result.stdout


def test_readable_code_example_requires_initial_state_sequence_and_outcome():
    text = _historical_sample_text()
    text = text.replace("扫描开始时", "扫描开始", 1)
    doc = Path(tempfile.mkdtemp()) / "superficial-example.md"
    doc.write_text(text, encoding="utf-8")
    result = run(doc)
    assert result.returncode == 1
    assert "示例须包含初始状态、输入序列和预期结果" in result.stdout


def test_restructured_shipped_m02_example_is_accepted():
    text = _historical_sample_text()
    module = text.split('<a id="m02"></a>', 1)[1].split("#### M03", 1)[0]
    assert module.index("**2. 推演示例") < module.index("```pascal")
    doc = Path(tempfile.mkdtemp()) / "worked-example-before-code.md"
    doc.write_text(text, encoding="utf-8")
    assert run(doc).returncode == 0


def test_module_fourth_part_cannot_be_missing_or_out_of_order():
    text = _historical_sample_text()
    assert "**4. 与其他程序的交互**" in text
    assert "**4. 与其他机台的交互**" not in text
    legacy_text = text.replace("**4. 与其他程序的交互**", "**4. 与其他机台的交互**", 1)
    legacy_doc = Path(tempfile.mkdtemp()) / "legacy-module-part.md"
    legacy_doc.write_text(legacy_text, encoding="utf-8")
    legacy_result = run(legacy_doc)
    assert legacy_result.returncode == 1
    assert "模块四部分" in legacy_result.stdout
    text = text.replace("**2. 推演示例**", "**2. 交互示例**", 1)
    doc = Path(tempfile.mkdtemp()) / "bad-module-parts.md"
    doc.write_text(text, encoding="utf-8")
    result = run(doc)
    assert result.returncode == 1
    assert "模块四部分" in result.stdout


def test_each_module_part_missing_duplicate_or_reordered_fails():
    base = _historical_sample_text()
    titles = (
        "**1. 功能定位**",
        "**2. 推演示例**",
        "**3. 实现与逐句说明**",
        "**4. 与其他程序的交互**",
    )
    mutations = []
    for title in titles:
        mutations.append(base.replace(title, "**未填写**", 1))
        mutations.append(base.replace(title, title + "\n\n" + title, 1))
    swapped = base.replace(titles[0], "__PART_ONE__", 1)
    swapped = swapped.replace(titles[1], titles[0], 1).replace("__PART_ONE__", titles[1], 1)
    mutations.append(swapped)
    for index, text in enumerate(mutations):
        doc = Path(tempfile.mkdtemp()) / f"bad-parts-{index}.md"
        doc.write_text(text, encoding="utf-8")
        result = run(doc)
        assert result.returncode == 1, f"mutation {index} unexpectedly passed"
        assert "模块四部分" in result.stdout


def test_module_parts_are_not_directory_headings():
    text = _historical_sample_text().replace("**1. 功能定位**", "##### 1. 功能定位", 1)
    doc = Path(tempfile.mkdtemp()) / "headings.md"
    doc.write_text(text, encoding="utf-8")
    result = run(doc)
    assert result.returncode == 1
    assert "模块四部分必须使用普通粗体小标题" in result.stdout


def test_forbidden_omission_fails():
    text = _historical_sample_text()
    text = text.replace("## 七、关键 MFB/FB", "## 七、关键 MFB/FB\n\n其余略。", 1)
    with tempfile.TemporaryDirectory() as td:
        doc = Path(td) / "h.md"
        doc.write_text(text, encoding="utf-8")
        result = run(doc)
    assert result.returncode == 1
    assert "禁止省略用语" in result.stdout


def test_missing_src_marker_fails():
    text = _historical_sample_text()
    text = text.replace("<!-- src:", "<!-- 源:", 10)
    with tempfile.TemporaryDirectory() as td:
        doc = Path(td) / "h.md"
        doc.write_text(text, encoding="utf-8")
        result = run(doc)
    assert result.returncode == 1
    assert "没有任何 <!-- src:" in result.stdout


def test_missing_two_pass_fails():
    text = _historical_sample_text()
    text = text.replace("**1. 功能定位**", "**用途**", 2).replace("**2. 推演示例**", "**代码**", 2)
    with tempfile.TemporaryDirectory() as td:
        doc = Path(td) / "h.md"
        doc.write_text(text, encoding="utf-8")
        result = run(doc)
    assert result.returncode == 1
    assert "模块四部分不完整" in result.stdout


def test_segment_without_line_bullets_fails():
    text = _historical_sample_text()
    kept = [ln for ln in text.splitlines() if not (ln.strip().startswith("- ") and "`" in ln)]
    with tempfile.TemporaryDirectory() as td:
        doc = Path(td) / "h.md"
        doc.write_text("\n".join(kept) + "\n", encoding="utf-8")
        result = run(doc)
    assert result.returncode == 1
    assert "逐句说明缺失或未覆盖执行单元" in result.stdout


def _variant(*replacements):
    text = _historical_sample_text()
    for old, new in replacements:
        assert old != new, f"replacement must mutate the fixture: {old!r}"
        assert old in text, f"fixture anchor not found: {old!r}"
        updated = text.replace(old, new, 1)
        assert updated != text, f"fixture mutation failed: {old!r}"
        text = updated
    td = Path(tempfile.mkdtemp()) / "h.md"
    td.write_text(text, encoding="utf-8")
    return td


def test_obvious_assignment_without_comment_is_rejected():
    doc = _variant(("    yClampValve := TRUE;              // 本段置位夹紧阀输出，清除条件未出现在当前源码", "    yClampValve := TRUE;"))
    result = run(doc)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "缺少有效行内注释" in result.stdout
    assert "逐句说明少于代码行" not in result.stdout


def test_syntactic_inline_comment_fails_even_when_present():
    for bad in (
        "把右边赋给左边",
        "条件成立进入分支",
        "结束判断",
        "语句",
        "否则：以上条件均不成立时执行",
        "条件判断开始：判断下列条件是否全部成立",
        "循环开始：按次数递增遍历",
    ):
        doc = _variant(("// 本段置位夹紧阀输出，清除条件未出现在当前源码", f"// {bad}"))
        result = run(doc)
        assert result.returncode == 1, f"accepted: {bad}\n{result.stdout}"
        assert "行内注释只是语法复述" in result.stdout


def test_nontrivial_inline_comment_is_accepted():
    for good in (
        "当前步序 20 请求夹紧时保持阀输出，具体清除条件需核对其他写入点",
        "当前片段只证明阀输出被置位，复位条件未知",
        "当前输出在本分支保持，其他写入点是否撤销它仍需核对",
    ):
        doc = _variant(("// 本段置位夹紧阀输出，清除条件未出现在当前源码", f"// {good}"))
        result = run(doc)
        assert result.returncode == 0, result.stdout + result.stderr


def test_field_only_comment_is_rejected_as_low_value():
    doc = _variant((
        "    yClampValve := TRUE;              // 本段置位夹紧阀输出，清除条件未出现在当前源码",
        "    yClampValve := TRUE;              // 将 yClampValve 赋值为 TRUE",
    ))
    result = run(doc)
    assert result.returncode == 1, result.stdout
    assert "注释信息价值低" in result.stdout


def test_condition_state_and_risk_comment_is_accepted():
    doc = _variant((
        "    yClampValve := TRUE;              // 本段置位夹紧阀输出，清除条件未出现在当前源码",
        "    yClampValve := TRUE;              // 步序 20 请求夹紧时保持输出，等待到位反馈后才允许推进",
    ))
    result = run(doc)
    assert result.returncode == 0, result.stdout + result.stderr


def test_string_literal_slashes_do_not_count_as_inline_comments():
    failures = []
    for code in (
        'sPath := "http://example.test";',
        'sText := "say ""//"" now";',
        "sText := 'say ''//'' now';",
        r'sText := "say \"//\" now";',
    ):
        doc = _variant((
            "    yClampValve := TRUE;              // 本段置位夹紧阀输出，清除条件未出现在当前源码",
            f"    {code}",
        ))
        result = run(doc)
        if result.returncode != 1 or "缺少有效行内注释" not in result.stdout:
            failures.append(f"{code}: {result.stdout}")
    assert not failures, "string literal was treated as comment:\n" + "\n".join(failures)


def test_real_comment_after_string_literal_is_accepted():
    doc = _variant((
        "    yClampValve := TRUE;              // 本段置位夹紧阀输出，清除条件未出现在当前源码",
        '    sPath := "http://example.test"; // 此路径只用于说明，工程取值未知',
    ), (
        '- `yClampValve := TRUE`：', '- `sPath := "http://example.test"`：',
    ))
    result = run(doc)
    assert result.returncode == 0, result.stdout + result.stderr


def test_pure_structure_closures_require_note_by_default():
    text = _historical_sample_text()
    assert "    END_IF;\nEND_IF;" in text
    assert "END_IF; //" not in text
    # 已确认的新默认：结构闭合行也要 // AI: 尾注；历史选择性口径须显式开关。
    with tempfile.TemporaryDirectory() as td:
        doc = Path(td) / 'unannotated-closures.md'
        doc.write_text(text, encoding='utf-8')
        default = run(doc, default=True)
        assert default.returncode == 1, default.stdout
        assert "默认逐行注释缺失" in default.stdout
        legacy = run(doc)
        assert legacy.returncode == 0, legacy.stdout + legacy.stderr
    shipped = run(SAMPLE, default=True)
    assert shipped.returncode == 0, shipped.stdout + shipped.stderr


def test_closure_with_following_statement_requires_comment():
    doc = _variant((
        "    END_IF;\nEND_IF;",
        "    END_IF; xClampAlarm := TRUE;\nEND_IF;",
    ))
    result = run(doc)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "缺少有效行内注释" in result.stdout


def test_else_requires_inline_comment():
    source = "        iStep := 30;                  // 新步号可被本扫描后续逻辑立即读取，M03 是否在其后执行仍需任务顺序证据\n    END_IF;"
    with_else = "        iStep := 30;                  // 新步号可被本扫描后续逻辑立即读取，M03 是否在其后执行仍需任务顺序证据\n    ELSE // 到位反馈未出现时不推进步序\n        iStep := 20; // 保持流程停留于夹紧步，等待下一次扫描\n    END_IF;"
    explanation = ('**逐句看**', '**逐句看**\n\n- `ELSE`：到位为假时走等待分支。\n- `iStep := 20`：明确写入夹紧步号。')
    accepted_doc = _variant((source, with_else), explanation)
    accepted = run(accepted_doc)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr

    doc = _variant((source, with_else), explanation, ("    ELSE // 到位反馈未出现时不推进步序", "    ELSE"))
    result = run(doc)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "缺少有效行内注释" in result.stdout


def test_elsif_requires_inline_comment():
    source = "        iStep := 30;                  // 新步号可被本扫描后续逻辑立即读取，M03 是否在其后执行仍需任务顺序证据"
    with_elsif = source + "\n    ELSIF xRetry THEN // 重试许可有效时重新进入夹紧等待路径"
    explanation = ('**逐句看**', '**逐句看**\n\n- `ELSIF xRetry THEN`：到位为假且重试许可为真时进入此支。')
    accepted = run(_variant((source, with_elsif), explanation))
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr

    doc = _variant(
        (source, with_elsif),
        explanation,
        ("ELSIF xRetry THEN // 重试许可有效时重新进入夹紧等待路径", "ELSIF xRetry THEN"),
    )
    result = run(doc)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "缺少有效行内注释" in result.stdout


def test_standalone_comment_cannot_replace_inline_comment():
    doc = _variant((
        "    yClampValve := TRUE;              // 本段置位夹紧阀输出，清除条件未出现在当前源码",
        "    // 夹紧请求保持到复位逻辑清除\n    yClampValve := TRUE;",
    ))
    result = run(doc)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "缺少有效行内注释" in result.stdout


def test_segment_without_example_fails():
    doc = _variant(("**2. 推演示例**", "**补充说明**"))
    result = run(doc)
    assert result.returncode == 1
    assert "模块四部分不完整" in result.stdout or "缺少情境示例" in result.stdout


def test_missing_source_block_inventory_fails():
    doc = _variant(("**本工位源码块覆盖清单**", "**清单**"))
    result = run(doc)
    assert result.returncode == 1
    assert "缺少源码块覆盖清单" in result.stdout


def test_emoji_budget_is_not_a_gate_but_code_emoji_fails():
    text = _historical_sample_text()
    text += "\n" + "\n".join("- 🚀 阅读提示" for _ in range(41)) + "\n"
    with tempfile.TemporaryDirectory() as td:
        doc = Path(td) / "h.md"
        doc.write_text(text, encoding="utf-8")
        result = run(doc)
    assert result.returncode == 0, result.stdout + result.stderr

    text2 = _historical_sample_text().replace("    yClampValve := TRUE;", "    yClampValve := TRUE; // ✅ 置位", 1)
    with tempfile.TemporaryDirectory() as td:
        doc = Path(td) / "h.md"
        doc.write_text(text2, encoding="utf-8")
        result = run(doc)
    assert result.returncode == 1
    assert "代码块或表格字段内出现表情" in result.stdout


def test_chapter_without_emoji_is_allowed():
    doc = _variant(("## 七、关键 MFB/FB 🧩", "## 七、关键 MFB/FB"))
    result = run(doc)
    assert result.returncode == 0, result.stdout + result.stderr


def test_emoji_in_inline_code_fails():
    doc = _variant(("`xClampDone`", "`xClampDone ✅`"))
    result = run(doc)
    assert result.returncode == 1
    assert "行内代码中出现表情" in result.stdout or "代码块或表格字段内出现表情" in result.stdout


def test_emoji_is_rejected_in_metadata_identifiers_and_table_cells():
    source = """# 标题

> 文档类型：handbook
> 模板组合：HBK@2.2

## 九、未确认与证据

工程名称：产线 🚀
对象 ID：M01🚀
证据等级：已确认 🚀

| 字段 | 值 |
|---|---|
| 变量 | xReady 🚀 |
"""
    with tempfile.TemporaryDirectory() as td:
        doc = Path(td) / "h.md"
        doc.write_text(source, encoding="utf-8")
        result = run(doc)
    assert result.returncode == 1
    assert "元数据、标识符、证据字段或表格字段" in result.stdout


def test_tilde_fences_are_scanned_and_helpful_heading_hints_are_allowed():
    source = """# 标题

> 文档类型：handbook
> 模板组合：HBK@2.2

## 九、未确认与证据 🔎

- 💡 核对写入点后再确认复位路径。

~~~st
xReady := TRUE; // 🚀 非代码注释
~~~
"""
    with tempfile.TemporaryDirectory() as td:
        doc = Path(td) / "h.md"
        doc.write_text(source, encoding="utf-8")
        result = run(doc)
    assert result.returncode == 1
    assert "代码块或表格字段内出现表情" in result.stdout


def test_normal_prose_can_quote_emoji_policy_without_false_positive():
    text = _historical_sample_text() + "\n正文引用规范示例：“xReady 🚀”作为反例，不代表真实变量。\n"
    with tempfile.TemporaryDirectory() as td:
        doc = Path(td) / "h.md"
        doc.write_text(text, encoding="utf-8")
        result = run(doc)
    assert result.returncode == 0, result.stdout + result.stderr


def test_broken_anchor_and_missing_toc_fail():
    doc = _variant(('<a id="m02"></a>', '<a id="x02"></a>'))
    result = run(doc)
    assert result.returncode == 1
    assert "交叉引用失效：# m02" in result.stdout

    doc2 = _variant(("## 目录", "## 内容"))
    result2 = run(doc2)
    assert result2.returncode == 1
    assert "缺少目录" in result2.stdout


def test_alarm_matrix_columns_required():
    doc = _variant(("| 报警码 | 报警 / 异常 | 触发条件 | 影响对象 | 输出处理 | 复位方式 | 恢复起点 | 证据 |",
                    "| 报警 | 条件 | 影响 | 处理 | 复位 | 起点 | 证据 | 备 |"))
    result = run(doc)
    assert result.returncode == 1
    assert "报警矩阵缺少" in result.stdout


def test_final_rejects_unfinished_status():
    text = _historical_sample_text()
    old = '| M02 | 夹紧控制 | obj2 | 示例可见 6 行 | 已讲 | 本次范围 |'
    assert old in text
    text = text.replace(old, old.replace('已讲', '受保护'), 1)
    with tempfile.TemporaryDirectory() as td:
        doc = Path(td) / "h.md"
        doc.write_text(text, encoding="utf-8")
        assert run(doc).returncode == 0, "中间稿应允许未完成状态"
        result = run(doc, "--final")
    assert result.returncode == 1
    assert "最终交付仍有未完成覆盖状态" in result.stdout


def test_emoji_forbidden_fields_cannot_be_laundered_by_policy_quotes():
    sys.path.insert(0, str(ROOT / "scripts"))
    from validate_handbook import emoji_errors
    for line in (
        '工程名称：产线 🚀（规则示例：“工程名称可为任意文本”）',
        '证据等级：已确认 🚀（反例，不代表真实等级）',
        'xReady: TRUE 🚀（规则示例：“引用文字”）',
        '正文引用：“xReady 🚀”作为反例。工程名称：产线 🚀',
        '正文引用：“xReady 🚀”作为反例。额外 🚀',
        '| M03 | ✅ 已讲 |',
        '```st 🚀\nx := TRUE;\n```',
        '~~~text 🚀\n普通文本\n~~~',
    ):
        assert emoji_errors(line), line


def test_emoji_id_headings_and_precise_prose_quotes_are_allowed():
    sys.path.insert(0, str(ROOT / "scripts"))
    from validate_handbook import emoji_errors
    for line in ('## 四、对象 ID 与实例 🧩', '> 💡 核对对象 ID 与调用实例。',
                 '正文引用规范示例：“xReady 🚀”作为反例，不代表真实变量。',
                 '正文引用：“工程名称：产线 🚀”是违规字段示例。',
                 '## 五、xReady 的写入点 🔗', '> ⚠️ xReady 未置位', '- ✅ 已确认：核对完成'):
        assert not emoji_errors(line), (line, emoji_errors(line))


def test_emoji_table_status_guidance_agrees_with_gate():
    text = (ROOT / "references/handbook-guide.md").read_text(encoding="utf-8")
    assert "状态列可用" not in text
    assert "状态列使用纯文字" in text


def test_line_explanation_body_cannot_be_replaced_by_other_bullets():
    base = SAMPLE.read_text(encoding='utf-8')
    start = base.index('**逐句看**')
    end = base.index('**状态后果与边界**', start)
    for replacement in ('', '**逐句看**\n\n', '**逐句看**\n\n- `iStep`：设置步号。\n\n'):
        text = base[:start] + replacement + base[end:]
        assert text != base
        with tempfile.TemporaryDirectory() as td:
            doc = Path(td) / 'missing-explanations.md'
            doc.write_text(text, encoding='utf-8')
            result = run(doc)
        assert result.returncode == 1, result.stdout
        assert '逐句说明' in result.stdout, result.stdout


def test_claimed_module_must_have_matching_body():
    base = SAMPLE.read_text(encoding='utf-8')
    row = '| M99 | 未展示模块 | obj99 | 99–100 | 已讲 | 无 |'
    anchor = '**本工位源码块覆盖清单**'
    assert anchor in base
    pos = base.index('<a id="m02"></a>', base.index(anchor))
    text = base[:pos] + row + '\n\n' + base[pos:]
    with tempfile.TemporaryDirectory() as td:
        doc = Path(td) / 'false-coverage.md'
        doc.write_text(text, encoding='utf-8')
        result = run(doc)
    assert result.returncode == 1, result.stdout
    assert '已讲模块缺少正文' in result.stdout, result.stdout


def test_deleted_module_cannot_still_be_claimed_complete():
    base = SAMPLE.read_text(encoding='utf-8')
    start = base.index('<a id="m02"></a>')
    end = base.index('<a id="m03"></a>', start)
    text = base[:start] + base[end:]
    with tempfile.TemporaryDirectory() as td:
        doc = Path(td) / 'deleted-module.md'
        doc.write_text(text, encoding='utf-8')
        result = run(doc)
    assert result.returncode == 1, result.stdout
    assert '已讲模块缺少正文' in result.stdout, result.stdout


def test_all_inventory_tables_and_merged_ids_are_checked():
    base = SAMPLE.read_text(encoding='utf-8')
    original = '| M02 | 夹紧控制 | obj2 | 示例可见 6 行 | 已讲 | 本次范围 |'
    for ids in ('M02–M99', 'M02、M99'):
        text = base.replace(original, original.replace('M02', ids), 1)
        with tempfile.TemporaryDirectory() as td:
            doc = Path(td) / 'merged.md'
            doc.write_text(text, encoding='utf-8')
            result = run(doc)
        assert result.returncode == 1 and 'M99' in result.stdout, result.stdout
    table = ('**W02 本工位源码块覆盖清单**\n\n'
             '| 编号 | 模块 | 对象 ID | 范围 | 状态 | 备注 |\n'
             '|---|---|---|---|---|---|\n'
             '| M99 | 幽灵模块 | obj99 | 99–100 | 已讲 | 无 |\n\n')
    for anchor in ('<a id="m03"></a>', '<a id="ch5"></a>'):
        text = base.replace(anchor, table + anchor, 1)
        with tempfile.TemporaryDirectory() as td:
            doc = Path(td) / 'second-table.md'
            doc.write_text(text, encoding='utf-8')
            result = run(doc)
        assert result.returncode == 1 and 'M99' in result.stdout, result.stdout


def test_template_coverage_rows_map_to_module_ids():
    text = (ROOT / 'references/template-handbook.md').read_text(encoding='utf-8')
    assert '| B0 |' not in text
    assert '| M01 |' in text


def main() -> int:
    tests = [
        test_all_inventory_tables_and_merged_ids_are_checked,
        test_template_coverage_rows_map_to_module_ids,
        test_line_explanation_body_cannot_be_replaced_by_other_bullets,
        test_claimed_module_must_have_matching_body,
        test_deleted_module_cannot_still_be_claimed_complete,
        test_emoji_forbidden_fields_cannot_be_laundered_by_policy_quotes,
        test_emoji_id_headings_and_precise_prose_quotes_are_allowed,
        test_emoji_table_status_guidance_agrees_with_gate,
        test_each_module_anchor_is_unique_and_linkable,
        test_module_heading_must_not_link_to_itself,
        test_module_heading_without_jump_entry_fails,
        test_chapter_without_matching_anchor_fails,
        test_analogy_is_optional,
        test_analogy_must_follow_line_by_line_explanation,
        test_sample_handbook_passes,
        test_fb_topic_sample_passes,
        test_pure_signal_flow_document_does_not_need_handbook_chapters,
        test_registered_template_composition_is_accepted,
        test_unknown_template_id_fails,
        test_unregistered_template_combination_fails,
        test_included_alarm_matrix_still_requires_its_fields,
        test_unsafe_force_io_or_safety_bypass_recommendation_fails,
        test_positive_unsafe_recommendations_fail,
        test_read_only_safety_boundary_is_allowed,
        test_negated_safety_list_is_allowed,
        test_missing_chapter_fails,
        test_chapter_outside_declared_scope_fails,
        test_chapters_must_follow_declared_order_but_may_skip,
        test_every_module_has_four_plain_bold_subheadings,
        test_readable_code_requires_worked_example_before_plc_source,
        test_readable_code_example_requires_initial_state_sequence_and_outcome,
        test_restructured_shipped_m02_example_is_accepted,
        test_module_fourth_part_cannot_be_missing_or_out_of_order,
        test_each_module_part_missing_duplicate_or_reordered_fails,
        test_module_parts_are_not_directory_headings,
        test_forbidden_omission_fails,
        test_missing_src_marker_fails,
        test_missing_two_pass_fails,
        test_segment_without_line_bullets_fails,
        test_obvious_assignment_without_comment_is_rejected,
        test_syntactic_inline_comment_fails_even_when_present,
        test_nontrivial_inline_comment_is_accepted,
        test_field_only_comment_is_rejected_as_low_value,
        test_condition_state_and_risk_comment_is_accepted,
        test_string_literal_slashes_do_not_count_as_inline_comments,
        test_real_comment_after_string_literal_is_accepted,
        test_pure_structure_closures_require_note_by_default,
        test_closure_with_following_statement_requires_comment,
        test_else_requires_inline_comment,
        test_elsif_requires_inline_comment,
        test_standalone_comment_cannot_replace_inline_comment,
        test_segment_without_example_fails,
        test_missing_source_block_inventory_fails,
        test_emoji_budget_is_not_a_gate_but_code_emoji_fails,
        test_chapter_without_emoji_is_allowed,
        test_emoji_in_inline_code_fails,
        test_emoji_is_rejected_in_metadata_identifiers_and_table_cells,
        test_tilde_fences_are_scanned_and_helpful_heading_hints_are_allowed,
        test_normal_prose_can_quote_emoji_policy_without_false_positive,
        test_broken_anchor_and_missing_toc_fail,
        test_alarm_matrix_columns_required,
        test_final_rejects_unfinished_status,
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
