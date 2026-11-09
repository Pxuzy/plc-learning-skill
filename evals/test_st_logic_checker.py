#!/usr/bin/env python3
"""ST 静态逻辑检查器的回归测试：正文规则、行号、注释/字符串不误判、CLI 契约。

全部用例通过 evals/_harness.run() 在进程内调用 main()，不起子进程（沙箱禁止管道）。
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_st_logic.py"

sys.path.insert(0, str(ROOT / "evals"))
from _harness import run  # noqa: E402

LEGAL = """\
FUNCTION_BLOCK FB_Counter
VAR_INPUT
    xEnable : BOOL;
END_VAR
VAR
    nCount : INT;
    xDone : BOOL;
    fbTimer : FB_TON;
END_VAR
fbTimer(IN := xEnable, PT := T#200MS);
IF xEnable AND NOT fbTimer.Q THEN
    nCount := nCount + 1;
ELSIF fbTimer.Q THEN
    xDone := TRUE;
END_IF;
CASE nCount OF
    0, 1: xDone := FALSE;
    2..5: xDone := TRUE;
ELSE
    xDone := FALSE;
END_CASE;
END_FUNCTION_BLOCK
"""


def check(text: str, *args: str):
    """写临时 .st，返回 harness 结果。"""
    with tempfile.TemporaryDirectory(prefix="plc-st-logic-") as directory:
        path = Path(directory) / "sample.st"
        path.write_text(text, encoding="utf-8")
        return run(SCRIPT, str(path), *args)


def codes(result) -> list[str]:
    out = []
    for line in result.stdout.splitlines():
        parts = line.split()
        for index, token in enumerate(parts):
            if token.startswith("STB") and len(token) == 6:
                out.append(token)
    return out


def assert_has(result, code: str, line: int | None = None):
    blob = result.stdout + result.stderr
    assert code in blob, blob
    if line is not None:
        assert f":{line}: " in blob, f"缺少行号 {line}：{blob}"
    return result


def test_legal_fragment_has_no_findings():
    result = check(LEGAL)
    assert result.returncode == 0, result.stdout + result.stderr
    assert codes(result) == [], result.stdout
    assert "共检查 1 个文件：0 错误、0 警告、0 提示" in result.stdout, result.stdout


def test_missing_end_if_reports_opening_line():
    text = "xStart := TRUE;\nIF xStart THEN\n    xRun := TRUE;\n"
    result = check(text)
    assert result.returncode == 1, result.stdout + result.stderr
    assert_has(result, "STB001", 2)


def test_extra_end_if_reports_its_own_line():
    result = check("IF xStart THEN\n    xRun := TRUE;\nEND_IF;\nEND_IF;\n")
    assert_has(result, "STB001", 4)


def test_case_duplicate_label():
    text = ("CASE nStep OF\n"
            "    1: xRun := TRUE;\n"
            "    2: xRun := FALSE;\n"
            "    1: xRun := TRUE;\n"
            "ELSE\n"
            "    xRun := FALSE;\n"
            "END_CASE;\n")
    result = check(text)
    assert result.returncode == 1, result.stdout + result.stderr
    assert_has(result, "STB003", 4)
    assert "首次出现在第 2 行" in result.stdout, result.stdout


def test_case_reversed_range():
    text = ("CASE nStep OF\n"
            "    10..1: xRun := TRUE;\n"
            "ELSE\n"
            "    xRun := FALSE;\n"
            "END_CASE;\n")
    result = check(text)
    assert result.returncode == 1, result.stdout + result.stderr
    assert_has(result, "STB004", 2)


def test_case_without_else_is_warn_only():
    text = ("CASE nStep OF\n"
            "    1: xRun := TRUE;\n"
            "    2: xRun := FALSE;\n"
            "END_CASE;\n")
    result = check(text)
    assert result.returncode == 0, result.stdout + result.stderr
    assert_has(result, "STB002", 1)
    assert "0 错误、1 警告" in result.stdout, result.stdout


STATE_TABLES = """\
TYPE ST_StateNode :
STRUCT
    nState : INT;
    nParent : INT;
    xLeaf : BOOL;
    nTimeoutMS : INT;
END_STRUCT
END_TYPE
VAR
    aStationNodes : ARRAY[0..7] OF ST_StateNode;
    aStationTrans : ARRAY[0..15] OF ST_Transition;
    nInitState : INT;
END_VAR
aStationNodes[0].nState := 0;
aStationNodes[0].nParent := -1;
aStationNodes[0].xLeaf := TRUE;
aStationNodes[0].nTimeoutMS := 500;
aStationNodes[1].nState := 10;
aStationNodes[1].nParent := 0;
aStationNodes[1].xLeaf := TRUE;
aStationTrans[0].nFrom := 0;
aStationTrans[0].nEvent := 1;
aStationTrans[0].wGuard := 0;
aStationTrans[0].wBlock := 0;
aStationTrans[0].nTo := 10;
"""


def test_state_tables_legal_baseline_is_clean():
    result = check(STATE_TABLES)
    assert result.returncode == 0, result.stdout + result.stderr
    assert codes(result) == [], result.stdout


def test_state_reference_outside_node_table():
    text = STATE_TABLES.replace("aStationTrans[0].nTo := 10;",
                                "aStationTrans[0].nTo := 99;")
    result = check(text)
    assert result.returncode == 1, result.stdout + result.stderr
    assert_has(result, "STB005", 25)


def test_duplicate_transition_edge():
    text = STATE_TABLES + ("aStationTrans[1].nFrom := 0;\n"
                           "aStationTrans[1].nEvent := 1;\n"
                           "aStationTrans[1].wGuard := 0;\n"
                           "aStationTrans[1].wBlock := 0;\n"
                           "aStationTrans[1].nTo := 10;\n")
    result = check(text)
    assert result.returncode == 1, result.stdout + result.stderr
    assert_has(result, "STB006")
    assert "重复转移" in result.stdout, result.stdout


def test_unreachable_leaf_state():
    text = STATE_TABLES.replace("aStationNodes[0].nParent := -1;",
                               "aStationNodes[0].nParent := -1;") + (
        "aStationNodes[2].nState := 20;\n"
        "aStationNodes[2].nParent := 0;\n"
        "aStationNodes[2].xLeaf := TRUE;\n")
    result = check(text)
    assert result.returncode == 0, result.stdout + result.stderr
    assert_has(result, "STB007")
    assert "不可达叶子状态 20" in result.stdout, result.stdout


def test_composite_state_without_children():
    text = STATE_TABLES + ("aStationNodes[3].nState := 30;\n"
                           "aStationNodes[3].nParent := 0;\n"
                           "aStationNodes[3].xLeaf := FALSE;\n")
    result = check(text)
    assert_has(result, "STB008")
    assert "复合状态 30" in result.stdout, result.stdout


def test_parent_self_reference_and_cycle():
    text = STATE_TABLES + ("aStationNodes[4].nState := 40;\n"
                           "aStationNodes[4].nParent := 40;\n"
                           "aStationNodes[4].xLeaf := TRUE;\n")
    result = check(text)
    assert result.returncode == 1, result.stdout + result.stderr
    assert_has(result, "STB008")
    assert "指向自身" in result.stdout, result.stdout

    cycle = STATE_TABLES + ("aStationNodes[4].nState := 40;\n"
                            "aStationNodes[4].nParent := 50;\n"
                            "aStationNodes[5].nState := 50;\n"
                            "aStationNodes[5].nParent := 40;\n")
    result = check(cycle)
    assert result.returncode == 1, result.stdout + result.stderr
    assert_has(result, "STB008")
    assert "成环" in result.stdout, result.stdout


def test_negative_timeout():
    text = STATE_TABLES.replace("aStationNodes[0].nTimeoutMS := 500;",
                                "aStationNodes[0].nTimeoutMS := -5;")
    result = check(text)
    assert result.returncode == 1, result.stdout + result.stderr
    assert_has(result, "STB009")


def test_constant_index_out_of_bounds():
    text = ("VAR\n    aCodes : ARRAY[0..3] OF INT;\nEND_VAR\n"
            "aCodes[2] := 1;\n"
            "aCodes[7] := 2;\n")
    result = check(text)
    assert result.returncode == 1, result.stdout + result.stderr
    assert_has(result, "STB010", 5)
    assert "aCodes[7]" in result.stdout, result.stdout


def test_division_and_modulo_by_zero():
    result = check("VAR\n    nA : INT;\nEND_VAR\nnA := 10 / 0;\nnA := 10 MOD 0;\n")
    assert result.returncode == 1, result.stdout + result.stderr
    assert_has(result, "STB011", 4)
    assert result.stdout.count("STB011") == 2, result.stdout


def test_division_by_constant_variable_is_not_flagged():
    result = check("VAR\n    nA, nB : INT;\nEND_VAR\nnA := 10 / nB;\nnA := 10 / 0.5;\n")
    assert "STB011" not in result.stdout, result.stdout


def test_tautological_conditions():
    text = ("IF TRUE THEN\n    xA := TRUE;\nEND_IF;\n"
            "IF FALSE THEN\n    xB := TRUE;\nEND_IF;\n"
            "IF xC AND FALSE THEN\n    xD := TRUE;\nEND_IF;\n")
    result = check(text)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.count("STB012") == 3, result.stdout


def test_bool_never_reset_is_info_only():
    text = ("VAR\n    xLatch : BOOL;\n    xPulse : BOOL;\nEND_VAR\n"
            "xLatch := TRUE;\nxPulse := TRUE;\nxPulse := FALSE;\n")
    result = check(text)
    assert result.returncode == 0, result.stdout + result.stderr
    assert_has(result, "STB013", 2)
    assert "xLatch" in result.stdout and "xPulse" not in result.stdout.split("STB013")[1], \
        result.stdout


def test_unused_fb_instance_is_warn():
    text = ("VAR\n    fbUsed : FB_TON;\n    fbIdle : FB_TON;\nEND_VAR\n"
            "fbUsed(IN := TRUE, PT := T#100MS);\n")
    result = check(text)
    assert_has(result, "STB014")
    assert "fbIdle" in result.stdout, result.stdout
    assert "fbUsed" not in result.stdout.split("STB014")[1], result.stdout


def test_statement_after_return_is_unreachable():
    text = ("IF xFault THEN\n"
            "    RETURN;\n"
            "    xRun := TRUE;\n"
            "END_IF;\n")
    result = check(text)
    assert result.returncode == 0, result.stdout + result.stderr
    assert_has(result, "STB015", 3)


def test_return_as_last_statement_is_not_flagged():
    result = check("IF xFault THEN\n    RETURN;\nEND_IF;\n")
    assert "STB015" not in result.stdout, result.stdout


def test_zero_timer_preset():
    result = check("fbTimer(IN := TRUE, PT := T#0MS);\nfbSlow(IN := TRUE, PT := T#0S);\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.count("STB016") == 2, result.stdout


def test_zero_timer_preset_on_stopped_call_is_not_flagged():
    # IN := FALSE 的调用只是复位/停表，PT 给零是有意为之。
    text = ("fbStay(IN := FALSE, PT := T#0MS);\n"
            "fbStay(IN := FALSE,\n       Q => xQ,\n       PT := T#0MS);\n")
    result = check(text)
    assert "STB016" not in result.stdout, result.stdout


def test_comments_and_strings_do_not_produce_findings():
    text = ("(* IF x THEN\ntonStable(IN := TRUE, PT := T#0MS);\n"
            "CASE nStep OF 1: x := 10 / 0; END_CASE;\n*)\n"
            "// IF TRUE THEN\n"
            "sText := 'IF TRUE THEN 10 / 0';\n"
            "sNested := 'it''s (* not a comment';\n"
            "xRun := TRUE;\n")
    result = check(text)
    assert result.returncode == 0, result.stdout + result.stderr
    assert codes(result) == [], result.stdout


def test_nested_block_comments_keep_real_lines():
    text = "(* outer (* inner 'unterminated *) still comment *)\nIF TRUE THEN\n    xRun := TRUE;\nEND_IF;\n"
    result = check(text)
    assert_has(result, "STB012", 2)


def test_line_numbers_survive_comment_blankening():
    text = "(*\nline two\n*)\nIF xGo THEN\n    xRun := TRUE;\n"
    result = check(text)
    assert_has(result, "STB001", 4)


def test_json_output_shape_and_filtering():
    text = "IF TRUE THEN\n    xRun := TRUE;\nEND_IF;\n"
    result = check(text, "--json")
    payload = json.loads(result.stdout)
    assert set(payload) == {"files", "findings", "summary"}, payload
    assert payload["files"][0].endswith("sample.st"), payload["files"]
    assert payload["summary"] == {"files": 1, "errors": 0, "warnings": 1, "infos": 0}, payload
    assert payload["findings"][0]["code"] == "STB012", payload["findings"]
    assert {"file", "line", "severity", "code", "message"} == set(payload["findings"][0])

    filtered = check(text, "--json", "--min-severity", "error")
    assert json.loads(filtered.stdout)["findings"] == [], filtered.stdout


def test_quiet_prints_only_summary():
    text = "IF TRUE THEN\n    xRun := TRUE;\nEND_IF;\n"
    result = check(text, "--quiet")
    assert result.stdout.strip() == "共检查 1 个文件：0 错误、1 警告、0 提示", result.stdout


def test_directory_recursion_is_sorted_and_st_only():
    with tempfile.TemporaryDirectory(prefix="plc-st-logic-") as directory:
        root = Path(directory)
        (root / "sub").mkdir()
        (root / "b.st").write_text("IF TRUE THEN\nEND_IF;\n", encoding="utf-8")
        (root / "sub" / "a.st").write_text("IF FALSE THEN\nEND_IF;\n", encoding="utf-8")
        (root / "note.md").write_text("IF TRUE THEN\n", encoding="utf-8")
        result = run(SCRIPT, str(root))
        assert result.returncode == 0, result.stdout + result.stderr
        lines = [line for line in result.stdout.splitlines() if "STB012" in line]
        assert len(lines) == 2, result.stdout
        # 路径排序：b.st 先于 sub/a.st，且非 .st 文件不参与。
        assert re.match(r"^.*[/\\]b\.st:1: ", lines[0]), lines
        assert re.match(r"^.*[/\\]sub[/\\]a\.st:1: ", lines[1]), lines
        assert "note.md" not in result.stdout, result.stdout


def test_missing_path_is_exit_one():
    result = run(SCRIPT, str(ROOT / "no-such-file.st"))
    assert result.returncode == 1, result.stdout + result.stderr
    assert "找不到文件" in result.stderr, result.stderr


def test_bad_severity_is_exit_one():
    result = check("IF TRUE THEN\nEND_IF;\n", "--min-severity", "fatal")
    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stderr.strip(), result.stderr


def test_utf8_bom_and_crlf_keep_line_numbers():
    with tempfile.TemporaryDirectory(prefix="plc-st-logic-") as directory:
        path = Path(directory) / "crlf.st"
        path.write_bytes(b"\xef\xbb\xbfIF xGo THEN\r\n    xRun := TRUE;\r\n")
        result = run(SCRIPT, str(path))
        assert result.returncode == 1, result.stdout + result.stderr
        assert_has(result, "STB001", 1)


def main() -> int:
    tests = [test_legal_fragment_has_no_findings,
             test_missing_end_if_reports_opening_line,
             test_extra_end_if_reports_its_own_line,
             test_case_duplicate_label,
             test_case_reversed_range,
             test_case_without_else_is_warn_only,
             test_state_tables_legal_baseline_is_clean,
             test_state_reference_outside_node_table,
             test_duplicate_transition_edge,
             test_unreachable_leaf_state,
             test_composite_state_without_children,
             test_parent_self_reference_and_cycle,
             test_negative_timeout,
             test_constant_index_out_of_bounds,
             test_division_and_modulo_by_zero,
             test_division_by_constant_variable_is_not_flagged,
             test_tautological_conditions,
             test_bool_never_reset_is_info_only,
             test_unused_fb_instance_is_warn,
             test_statement_after_return_is_unreachable,
             test_return_as_last_statement_is_not_flagged,
             test_zero_timer_preset,
             test_zero_timer_preset_on_stopped_call_is_not_flagged,
             test_comments_and_strings_do_not_produce_findings,
             test_nested_block_comments_keep_real_lines,
             test_line_numbers_survive_comment_blankening,
             test_json_output_shape_and_filtering,
             test_quiet_prints_only_summary,
             test_directory_recursion_is_sorted_and_st_only,
             test_missing_path_is_exit_one,
             test_bad_severity_is_exit_one,
             test_utf8_bom_and_crlf_keep_line_numbers]
    failed = 0
    for test in tests:
        try:
            test()
        except Exception as exc:  # noqa: BLE001 - 汇总所有失败
            failed += 1
            print(f"FAIL {test.__name__}: {exc}")
        else:
            print(f"PASS {test.__name__}")
    print(f"{len(tests) - failed}/{len(tests)} passed")
    return int(failed > 0)


if __name__ == "__main__":
    raise SystemExit(main())
