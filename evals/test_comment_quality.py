#!/usr/bin/env python3
"""Strict PLC comment coverage, lexical boundaries and whole-document regressions."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _harness as harness

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_plc_comments.py"
# Historical selective-comment mutation fixture: strip only added AI tails;
# bundled positive examples are checked with the new default in test_default_annotations.
BASE = re.sub(r" // AI: [^\n]*", "", (ROOT / "references/example-handbook.md").read_text(encoding="utf-8"))
ANCHOR = "    yClampValve := TRUE;              // 本段置位夹紧阀输出，清除条件未出现在当前源码"
GOOD = "本示例请求保留到下一次扫描，是否另有撤销路径需核对其他写入点"


def run_text(body: str, lang: str = "st", extra: bool = False):
    assert ANCHOR in BASE
    if extra:
        text = BASE + f"\n<!-- src: none -->\n```{lang}\n{body}\n```\n"
    else:
        text = BASE.replace(ANCHOR, body, 1)
        # This helper tests inline-comment acceptance, not explanation coverage.
        # Keep the orthogonal source-key fixture in sync with changed statements;
        # dedicated handbook tests remove/mismatch explanations to test that gate.
        sys.path.insert(0, str(ROOT / 'scripts'))
        checker = harness.load(SCRIPT)
        units = getattr(checker, 'check_text')('```st\n' + body + '\n```')['blocks'][0]['required_units']
        notes = '\n'.join('- `' + u['source'].strip() + '`：仅为注释词法测试补齐语句定位，不作为教学语义样例。' for u in units)
        text = text.replace('**逐句看**', '**逐句看**\n\n' + notes, 1)
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "handbook.md"
        path.write_text(text, encoding="utf-8")
        # 本文件复核历史选择性注释夹具：用 --legacy-selective 保留 per-unit
        # 覆盖/质量/语义审查断言，只跳过新默认的逐行尾注门禁。
        return harness.run(ROOT / "scripts/validate_handbook.py", str(path), "--legacy-selective")


def expect(body: str, code: int = 1, lang: str = "st", extra: bool = False):
    result = run_text(body, lang, extra)
    assert result.returncode == code, f"{body!r}: exit={result.returncode}\n{result.stdout}{result.stderr}"
    return result.stdout


def test_original_three_bypasses():
    for suffix in ("", " // 执行当前操作", " // yClampValve"):
        expect("    yClampValve := TRUE;" + suffix)


def test_every_topic_and_language_alias_is_checked():
    for lang in ("st", "ST", "Pascal", "SCL", "Structured-Text", "structured_text", "iecst", "iec", "plc", "IL", "LD", "LAD", "FBD", "SFC"):
        expect("x := TRUE;", lang=lang, extra=True)
        expect("x := TRUE; // 执行当前操作", lang=lang, extra=True)
        expect("x := TRUE; // " + GOOD, code=0, lang=lang, extra=True)


def test_multiline_conditions_branches_calls_declarations_are_covered():
    for body in ("AND xReady", "OR xRetry THEN", "ELSE", "ELSIF xRetry THEN", "CASE nStep OF", "20:", "fbGate(IN := xReady);", "fbGate(", "IN := xReady,", "xReady : BOOL;", "VAR_INPUT", "END_IF; x := TRUE;", "END_IF; (* closure *) x := TRUE;", "END_VAR x := TRUE;", "x := TRUE; //", "x := TRUE; (* *)"):
        expect(body)
    for body in ("END_IF;", "END_FOR;", "END_CASE;", "END_WHILE;", "END_REPEAT;", "END_VAR", "END_FUNCTION_BLOCK", "END_PROGRAM", ");", "// 原有注释", "(* 原有\n多行注释 *)", ""):
        expect(body, code=0)


def test_lexical_slashes_escapes_and_block_comments():
    for body in (
        's := "http://a//b";',
        's := "say ""//"" now";',
        "s := 'say ''//'' now';",
        's := "say $"// literal";',
        "s := 'say $'// literal';",
        r's := "say \"// literal";',
        "(* // not inline *) x := TRUE;",
        "(* first\n// still block\n*) x := TRUE;",
        "(* outer (* // nested *) still block *) x := TRUE;",
    ):
        expect(body)
        expect(body + " // " + GOOD, code=0)
    expect("x := TRUE; (* 本路径把请求留给下一次扫描 *)", code=0)
    expect("x := TRUE; (* 本路径保留请求 (* // 原注释 *) 供下一扫描使用 *)", code=0)
    expect("x := TRUE; (* open\nremaining *)")
    expect("x := TRUE; (* unclosed")


def test_each_statement_on_a_physical_line_needs_its_own_comment():
    expect("x := TRUE; y := FALSE; // " + GOOD)
    expect("x := TRUE; END_IF; // " + GOOD)
    expect("IF x THEN y := FALSE; // " + GOOD)
    expect("x := TRUE; (* 本路径将请求留给下次扫描 *) y := FALSE; (* 本路径撤销旧结果以免后续读到陈旧状态 *)", code=0)
    expect("IF x THEN (* 只在请求出现时处理本次结果 *) y := FALSE; (* 撤销旧结果避免后续读到陈旧状态 *) END_IF;", code=0)


def test_append_only_numbered_notes_cover_each_unit_without_rewriting_source():
    expect("x := TRUE; y := FALSE; // 单元1：本次请求留给下次扫描消费 | 单元2：撤销旧结果，避免后续读取陈旧状态", code=0)
    expect("x := TRUE; y := FALSE; // 单元1：本次请求留给下次扫描消费")
    expect("x := TRUE; y := FALSE; // 单元1：本次请求留给下次扫描消费 | 单元1：撤销旧结果")
    expect("x := TRUE; y := FALSE; // 单元1：执行当前操作 | 单元2：撤销旧结果，避免后续读取陈旧状态")
    expect("x := TRUE; y := FALSE; // 单元1：未知 | 单元2：撤销旧结果，避免后续读取陈旧状态")


def test_identical_assignment_in_different_branches_can_share_business_note():
    raw = """```st
IF ShowCurrent THEN // AI: 选择即时照度示值
    PanelLightReady := TRUE; // AI: 标记照度示值可用
ELSE // AI: 选择平均照度示值
    PanelLightReady := TRUE; // AI: 标记照度示值可用
END_IF; // AI: 照度示值选择结束
```\n"""
    import importlib.util
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("comment_checker_business_style", ROOT / "scripts/check_plc_comments.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert not module.check_text(raw)["errors"]
    mutated = raw.replace("    PanelLightReady := TRUE;", "    PanelAirReady := TRUE;", 1)
    assert any("注释重复粘贴" in item for item in module.check_text(mutated)["errors"])


def test_generic_field_translation_unknown_and_copy_paste_rejected():
    for comment in ("执行当前操作", "处理本段逻辑", "条件成立执行", "yClampValve", "yClampValve TRUE", "将 yClampValve 赋值为 TRUE", "输出置 TRUE", "执行当前操作，未知", "yClampValve，未知", "未知", "此处作用未知"):
        expect("yClampValve := TRUE; // " + comment)
    expect("x := TRUE; // " + GOOD + "\ny := FALSE; // " + GOOD)
    expect("x := TRUE; // 执行当前操作，" + GOOD)


def test_unknown_suffix_does_not_launder_field_translation():
    for comment in ("将 yClampValve 赋值为 TRUE，作用未知", "将 yClampValve 赋值为 TRUE；此处作用未知", "yClampValve 为 TRUE，未知"):
        expect("yClampValve := TRUE; // " + comment)
    expect("yClampValve := TRUE; // 保留本次输出请求；其他路径是否撤销及其先后顺序未知", code=0)


def test_additional_field_translation_verbs_are_rejected():
    for comment in ("yClampValve 置 TRUE", "把 yClampValve 写 TRUE", "yClampValve 变为 TRUE", "给 yClampValve 赋 TRUE"):
        expect("yClampValve := TRUE; // " + comment)


def test_unrecognized_or_swallowed_plc_fences_fail_closed():
    for document in (
        "```text\nintro\n```st\nx := TRUE;\n```",
        "    ```st\n    x := TRUE;\n    ```",
        "> ```st\n> x := TRUE;\n> ```",
    ):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "doc.md"
            path.write_text(document, encoding="utf-8")
            result = harness.run(SCRIPT, str(path), "--final")
        assert result.returncode == 1, result.stdout
    expect("x := TRUE;", lang="{.st}", extra=True)
    expect("x := TRUE;", lang="iec61131", extra=True)
    expect("x := TRUE; // " + GOOD, code=0, lang="{.st}", extra=True)


def test_identical_code_repeated_across_blocks_does_not_require_rewording():
    block = "```st\nx := TRUE; // AI: " + GOOD + "\n```"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "doc.md"
        path.write_text(block + "\n\n" + block, encoding="utf-8")
        result = harness.run(SCRIPT, str(path))
    assert result.returncode == 0, result.stdout


def test_final_document_digest_is_exact_bytes_for_crlf_and_bom():
    import runpy
    checker = runpy.run_path(str(SCRIPT))
    for prefix in (b"", b"\xef\xbb\xbf"):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "doc.md"
            raw = "```st\nx := TRUE; // AI: " + GOOD + "\n```\n"
            path.write_bytes(prefix + raw.replace("\n", "\r\n").encode("utf-8"))
            decoded = path.read_bytes().decode("utf-8-sig")
            blocks = checker["check_text"](decoded)["blocks"]
            review = {"document_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "reviewer": "test-fixture", "blocks": [
                {"fence_line": b["line"], "code_sha256": b["sha256"], "status": "reviewed", "covered_lines": b["required_lines"],
                 "evidence": "explicit fixture", "rationale": "the assignment retains this request; reset absent in the supplied source", "issues": []}
                for b in blocks]}
            rp = Path(tmp) / "review.json"
            rp.write_text(json.dumps(review), encoding="utf-8")
            result = subprocess.run([sys.executable, "-B", str(SCRIPT), str(path), "--final", "--comment-review", str(rp)], capture_output=True, text=True)
            assert result.returncode == 0, result.stdout + result.stderr


def test_handbook_requires_inline_comment_on_each_executable_line():
    sys.path.insert(0, str(ROOT / "scripts"))
    from check_plc_comments import check_text

    missing = check_text('''```iecst
IF xReady THEN // 仅在准备好时进入分支
yStart := TRUE;
END_IF;
```''')
    assert any("缺少有效行内注释" in error and "yStart := TRUE" in error for error in missing["errors"]), missing

    complete = check_text('''```iecst
IF xReady THEN // 仅在准备好时进入分支
yStart := TRUE; // 本分支置位启动请求，实际消费者未给出
END_IF;
```''')
    assert not complete["errors"], complete["errors"]


def test_require_every_line_flag_rejects_uncommented_closure_lines():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "comments.md"
        path.write_text('''```iecst
IF xReady THEN // AI: 准备信号成立时进入分支
yStart := TRUE; // AI: 本路径置位启动请求，消费者未知
END_IF;
```''', encoding="utf-8")
        # 默认即逐行：结构闭合行缺 // AI: 尾注必须被拒，报新默认门禁。
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), str(path)], capture_output=True, text=True)
        assert result.returncode == 1 and "L4" in result.stdout and "默认逐行注释缺失" in result.stdout, result.stdout + result.stderr

        path.write_text('''```iecst
IF xReady THEN // AI: 准备信号成立时进入分支
yStart := TRUE; // AI: 本路径置位启动请求，消费者未知
END_IF; // AI: 结束当前 IF 结构，不产生新的赋值
```''', encoding="utf-8")
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), str(path)], capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr



def test_require_every_line_lexes_trailing_comments_and_multiline_code():
    checker = harness.load(SCRIPT)
    # Comments preceding later code do not cover that later code, even closures.
    for code in (
        "END_IF; (* 已结束许可分支 *) END_FOR;",
        'END_IF; s := "http://a//b";',
        "END_IF; //",
        "END_IF; (* *)",
        "END_IF; (* open\n// inside block\n*)",
    ):
        errors = checker.check_every_code_line("```iecst\n" + code + "\n```")
        assert errors and any("L2" in e and code.splitlines()[0] in e for e in errors), (code, errors)

    complete = """```iecst
// 原注释无需重复
(* metadata // not executable
   nested (* // still comment *)
*)
IF xReady // 以准备状态限制启动路径
AND xPermit THEN // 同时要求本次许可
fbStart( // 提交启动实例的本次输入
IN := xReady, // 将准备状态送入实例入口
PT := T#10MS // 本次使用十毫秒门槛
); (* 参数结束，输出供后续逻辑读取 *)
END_IF; (* 结束本次启动许可路径 *)
```
```text
END_IF;
```"""
    assert not checker.check_every_code_line(complete)
    for code in ('s := "http://a//b";', "(* // metadata *) END_IF;",
                 "(* first\n// still block\n*) END_IF;", "END_IF;"):
        errors = checker.check_every_code_line("```iecst\n" + code + "\n```")
        assert errors and "代码行缺少行内注释" in errors[-1], (code, errors)
    # A closed block note can cover preceding code; its internal // is payload.
    assert not checker.check_every_code_line(
        "```st\nEND_IF; (* 许可路径结束 (* // 原嵌套说明 *) *)\n```")


def test_require_every_line_quality_remains_distinct_and_opt_in():
    checker = harness.load(SCRIPT)
    assert not checker.check_text("```st\nEND_IF;\n```")["errors"]
    assert checker.check_every_code_line("```st\nEND_IF;\n```")
    for note in ("结束判断", "未知"):
        errors = checker.check_every_code_line("```st\nEND_IF; // " + note + "\n```")
        assert errors and all("代码行缺少行内注释" not in e for e in errors), errors
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "strict.md"
        path.write_text("```st\nEND_IF;\n```", encoding="utf-8")
        default = harness.run(SCRIPT, str(path))
        legacy = harness.run(SCRIPT, str(path), "--legacy-selective")
        # 新默认拒收未注释的闭合行；历史选择性口径需显式开关，二者仍可区分。
        assert default.returncode == 1, default.stdout
        assert str(path) in default.stdout and "L2" in default.stdout and "默认逐行注释缺失" in default.stdout
        assert legacy.returncode == 0, legacy.stdout

def test_library_positive_plc_blocks_are_all_checked():
    sys.path.insert(0, str(ROOT / "scripts"))
    from check_plc_comments import check_text
    block_count = 0
    files = [ROOT / "SKILL.md", *sorted((ROOT / "references").rglob("*.md"))]
    for path in files:
        report = check_text(path.read_text(encoding="utf-8"))
        block_count += len(report["blocks"])
        assert not report["errors"], f"{path.name}: {report['errors']}"
    assert block_count >= 7, "正例源码围栏不能全部改成 text 逃避校验"
    # 子目录参考同样纳入扫描；数量随资产增长，下面的下限只防“全部改成 text 逃避校验”。
    assert any("workflows" in p.as_posix() for p in files), "子目录参考未被扫描"


def test_original_comment_can_be_preserved_with_substantive_append_only_note():
    expect("x := TRUE; // 执行当前操作 // 教学补充：" + GOOD, code=0)
    expect("x := TRUE; // 原有说明 // 教学补充：执行当前操作")
    expect("x := TRUE; // 原有说明 // 教学补充：未知")


def test_review_is_not_claimed_by_deterministic_success():
    out = expect("x := TRUE; // " + GOOD, code=0)
    assert "语义审查" in out and "待" in out, out


def test_tilde_and_long_fences_cannot_hide_plc():
    with tempfile.TemporaryDirectory() as td:
        for opening, closing in (("~~~ST", "~~~"), ("````SCL", "````"), ("```ST title", "```")):
            path = Path(td) / "handbook.md"
            path.write_text(BASE + "\n<!-- src: none -->\n" + opening + "\nx := TRUE;\n" + closing + "\n", encoding="utf-8")
            result = harness.run(ROOT / "scripts/validate_handbook.py", str(path))
            assert result.returncode == 1, result.stdout


def test_final_requires_current_complete_semantic_review():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "h.md"
        path.write_text(BASE, encoding="utf-8")
        fence = BASE.splitlines().index("```pascal") + 1
        code = BASE.split("```pascal\n", 1)[1].split("```", 1)[0].rstrip("\n")
        review = {
            "document_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "reviewer": "test author",
            "blocks": [{"fence_line": fence, "code_sha256": hashlib.sha256(code.encode()).hexdigest(),
                        "status": "reviewed", "covered_lines": list(range(fence + 1, fence + 5)),
                        "evidence": "本文件步序表与夹紧片段，仅限虚构示例",
                        "rationale": "逐项核对入口、输出保持和向30步推进；其他写入点未提供", "issues": []}],
        }
        receipt = Path(td) / "review.json"
        receipt.write_text(json.dumps(review), encoding="utf-8")
        result = harness.run(ROOT / "scripts/validate_handbook.py", str(path), "--final", "--legacy-selective")
        assert result.returncode == 1 and "语义审查" in result.stdout, result.stdout
        result = harness.run(ROOT / "scripts/validate_handbook.py", str(path), "--final", "--legacy-selective", "--comment-review", str(receipt))
        assert result.returncode == 0, result.stdout + result.stderr
        for field, value in (("status", "pending"), ("issues", ["意图未经源码支持"]), ("covered_lines", []), ("code_sha256", "stale"), ("evidence", "")):
            changed = json.loads(json.dumps(review))
            changed["blocks"][0][field] = value
            receipt.write_text(json.dumps(changed), encoding="utf-8")
            result = harness.run(ROOT / "scripts/validate_handbook.py", str(path), "--final", "--legacy-selective", "--comment-review", str(receipt))
            assert result.returncode == 1 and "语义审查" in result.stdout, result.stdout + result.stderr
        receipt.write_text(json.dumps({**review, "document_sha256": "stale"}), encoding="utf-8")
        result = harness.run(ROOT / "scripts/validate_handbook.py", str(path), "--final", "--legacy-selective", "--comment-review", str(receipt))
        assert result.returncode == 1 and "语义审查" in result.stdout, result.stdout


def review_fixture(raw, path, omitted=None):
    checker = harness.load(SCRIPT)
    blocks = checker.check_text(raw)["blocks"]
    entries = [{"fence_line": b["line"], "code_sha256": b["sha256"], "status": "reviewed",
                "covered_lines": b["required_lines"], "evidence": "虚构夹具；无调用表或符号表",
                "rationale": "仅核对本次赋值和条件范围，不推定外部业务或扫描顺序", "issues": []}
               for b in blocks]
    if omitted is not None:
        entries[0]["omitted_lines"] = omitted
    path.write_text(json.dumps({"document_sha256": checker.digest(raw), "reviewer": "fixture author",
                                "blocks": entries}), encoding="utf-8")


def test_closure_report_and_optional_omissions_match_both_final_entrypoints():
    raw = ("# 专题\n> 文档类型：handbook | 深度：代码深度\n> 模板组合：HBK@2.2\n"
           "## 范围\n<!-- src: none -->\n```st\nIF x THEN // x 为真才进入下面的清除路径\n"
           "yReady := FALSE; // 撤销旧结果，本次赋值后读取为假；业务用途未知\nEND_IF;\n```\n")
    checker = harness.load(SCRIPT)
    block = checker.check_text(raw)["blocks"][0]
    assert block.get("closure_lines") == [9], block
    assert block["required_lines"] == [7, 8], block
    with tempfile.TemporaryDirectory() as td:
        doc, receipt = Path(td) / "doc.md", Path(td) / "review.json"
        doc.write_text(raw, encoding="utf-8")
        for omitted in (None, [{"line": 9, "reason": "仅闭合条件范围，无新增动作"}]):
            review_fixture(raw, receipt, omitted)
            for script in (SCRIPT, ROOT / "scripts/validate_handbook.py"):
                result = harness.run(script, str(doc), "--final", "--legacy-selective", "--comment-review", str(receipt))
                assert result.returncode == 0, result.stdout
                assert "省略的纯结构闭合行 [9]" in result.stdout, result.stdout


def test_forged_closure_omissions_are_rejected_even_in_nonfinal_review():
    raw = "```st\nx := TRUE; // 本路径保留请求，撤销点未给出\nEND_IF;\n```\n"
    bad_records = ([{"line": 2, "reason": "没有业务资料"}], [{"line": 99, "reason": "闭合"}],
                   [{"line": 3, "reason": " "}], [{"line": 3, "reason": "闭合"}] * 2,
                   [{"line": "3", "reason": "闭合"}], "3", [None])
    with tempfile.TemporaryDirectory() as td:
        receipt = Path(td) / "review.json"
        for records in bad_records:
            review_fixture(raw, receipt, records)
            checker = harness.load(SCRIPT)
            errors = checker.check_review(raw, checker.check_text(raw)["blocks"], receipt, False)
            assert errors and any("omitted_lines" in e for e in errors), (records, errors)


def test_omissions_cannot_hide_nonclosure_or_existing_comments():
    checker = harness.load(SCRIPT)
    for source in ("END_IF; x := TRUE; // 本次结果只供后续读取，复位点未给出",
                   "END_IF; // 结束判断", "// 只有原注释", "", "ELSE // 本入口未命中时转入此路径",
                   "x : BOOL; // 暂存本次结果，初值未给出"):
        raw = "```st\n" + source + "\n```\n"
        with tempfile.TemporaryDirectory() as td:
            receipt = Path(td) / "review.json"
            review_fixture(raw, receipt, [{"line": 2, "reason": "声称只是闭合"}])
            report = checker.check_text(raw)
            assert not report["blocks"][0]["closure_lines"], report
            assert any("omitted_lines" in e for e in checker.check_review(raw, report["blocks"], receipt, True)), source


def test_execution_or_low_value_comment_cannot_be_waived_by_any_registration():
    for code in ("yReady := FALSE;", "yReady := FALSE; // 执行当前操作",
                 "END_IF; yReady := FALSE;"):
        raw = ("# 专题\n> 文档类型：handbook | 深度：代码深度\n> 模板组合：HBK@2.2\n"
               "## 范围\n<!-- src: none -->\n未解释行登记：待补资料\n```st\n" + code + "\n```\n")
        with tempfile.TemporaryDirectory() as td:
            doc, receipt = Path(td) / "doc.md", Path(td) / "review.json"
            doc.write_text(raw, encoding="utf-8")
            review_fixture(raw, receipt, [{"line": 8, "reason": "缺业务资料"}])
            for script in (SCRIPT, ROOT / "scripts/validate_handbook.py"):
                result = harness.run(script, str(doc), "--final", "--comment-review", str(receipt))
                assert result.returncode == 1, result.stdout
                assert "L8 单元 1/1" in result.stdout, result.stdout
                assert "omitted_lines" in result.stdout, result.stdout


def test_multiple_missing_units_are_distinguishable_in_all_reports():
    raw = "```st\na := 1; b := 2;\n```\n"
    report = harness.load(SCRIPT).check_text(raw)
    for label in ("L2 单元 1/2", "L2 单元 2/2"):
        assert any(label in e for e in report["errors"]), report
    units = report["blocks"][0].get("required_units")
    assert units and [(u["line"], u["unit"], u["of"], u["covered"]) for u in units] == [(2, 1, 2, False), (2, 2, 2, False)]
    raw = ("# 专题\n> 文档类型：handbook | 深度：代码深度\n> 模板组合：HBK@2.2\n"
           "## 范围\n<!-- src: none -->\n" + raw)
    with tempfile.TemporaryDirectory() as td:
        doc, receipt = Path(td) / "doc.md", Path(td) / "review.json"
        doc.write_text(raw, encoding="utf-8")
        review_fixture(raw, receipt)
        for script in (SCRIPT, ROOT / "scripts/validate_handbook.py"):
            for flags in ((), ("--final", "--comment-review", str(receipt))):
                result = harness.run(script, str(doc), *flags)
                assert result.returncode == 1, result.stdout
                for label in ("L7 单元 1/2", "L7 单元 2/2"):
                    assert label in result.stdout, result.stdout


def test_teaching_semantics_examples_are_evidence_bound_content_contract():
    text = (ROOT / "references/comment-quality.md").read_text(encoding="utf-8")
    for rule in ("已给上下文可用", "不能凭名称补出业务含义", "局部赋值不保证下一扫描", "不能断言机构动作",
                 "调用条件未知时", "执行行缺注释或低价值仍报错"):
        assert rule in text, rule
    pairs = (
        ("yClampValve := TRUE;", "解除夹紧由段外逻辑负责", "本段不撤销 TRUE，物理解除方式未知"),
        ("iStep := 30;", "下一扫描 iStep 必不等于 20", "若后续无改写且再次调用时值仍为 30，20 条件才不成立"),
        ("wAlarm = 0", "无报警条件", "只确认与 0 比较，编码含义未知"),
        ("xCheckEnable := xCheckEnable AND (wAlarm = 0);", "扫描尾自动恢复许可", "本次赋值只能保留真或写假，不能把旧假变真；业务用途未知"),
        ("本段调用", "每扫描执行", "若每扫描调用且入口成立，才会每扫描写入；调用顺序未给出"),
    )
    for source, bad, good in pairs:
        assert f"| `{source}` | {bad} | {good} |" in text, source
    assert "这组内容契约只锁定教学规则与样例，不证明词法器理解任意业务" in text


def main():
    tests = [value for name, value in globals().items() if name.startswith("test_")]
    failed = 0
    for test in tests:
        try:
            test()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {test.__name__}: {exc}")
        else:
            print(f"PASS {test.__name__}")
    print(f"{len(tests) - failed}/{len(tests)} passed")
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main())
