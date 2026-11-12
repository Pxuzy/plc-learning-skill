#!/usr/bin/env python3
"""CommonMark fence boundaries and ST rendering diagnostics."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# 个别用例直接 import scripts/ 下的辅助模块，不能依赖其它测试文件先改过 sys.path。
for extra in (ROOT / "scripts",):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))
SCRIPT = ROOT / "scripts" / "validate_st_rendering.py"


def run(text: str):
    with tempfile.TemporaryDirectory(prefix="plc-st-rendering-") as directory:
        document = Path(directory) / "doc.md"
        document.write_text(text, encoding="utf-8")
        return subprocess.run([sys.executable, "-B", str(SCRIPT), str(document)],
                              capture_output=True, text=True, cwd=ROOT, check=False)


def run_script(script: Path, text: str):
    with tempfile.TemporaryDirectory(prefix="plc-st-rendering-") as directory:
        document = Path(directory) / "doc.md"
        document.write_text(text, encoding="utf-8")
        return subprocess.run([sys.executable, "-B", str(script), str(document)],
                              capture_output=True, text=True, cwd=ROOT, check=False)


def expect_valid(text: str):
    result = run(text)
    assert result.returncode == 0, result.stdout + result.stderr


def expect_invalid_at(text: str, line: int):
    result = run(text)
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"第 {line} 行" in result.stdout, result.stdout


def test_screenshot_like_unclosed_st_has_opening_line_diagnostic():
    expect_invalid_at("```st\nxClamp := TRUE;\n", 1)


def test_format_checker_accepts_nested_short_fence_example():
    result = run_script(ROOT / "scripts" / "check_markdown_format.py",
                        "````st\nxClamp := TRUE;\n```\nexample marker\n````\n")
    assert result.returncode == 0, result.stdout


def test_layout_checker_uses_matching_fence_character_and_length():
    result = run_script(ROOT / "scripts" / "check_document_layout.py",
                        "````st\nxClamp := TRUE;\n```\nexample marker\n````\n")
    assert result.returncode == 0, result.stdout + result.stderr


def test_code_extraction_preserves_inner_short_fence_as_st_source():
    sys.path.insert(0, str(ROOT / "scripts"))
    from check_plc_comments import fences

    blocks = fences("````st\nxClamp := TRUE;\n```\nexample marker\n````\n")
    assert len(blocks) == 1
    assert blocks[0]["lang"] == "st"
    assert blocks[0]["closed"]
    assert blocks[0]["text"] == "xClamp := TRUE;\n```\nexample marker"


def test_long_backtick_fence_can_contain_short_backtick_example():
    expect_valid("````st\nxClamp := TRUE;\n```\nexample marker\n````\n")


def test_short_closer_does_not_close_long_opener():
    expect_valid("````st\nxClamp := TRUE;\n```\nstill ST\n````\n")


def test_backtick_and_tilde_fences_pair_only_with_same_character():
    expect_valid("```st\nxClamp := TRUE;\n~~~\nmore ST\n```\n")
    expect_valid("~~~st\nxClamp := TRUE;\n```\nmore ST\n~~~\n")


def test_cross_character_line_does_not_close_st_fence():
    expect_invalid_at("```st\nxClamp := TRUE;\n~~~\nstill open\n", 1)


def test_legal_st_block_is_recognized_and_accepted():
    result = run("~~~st\nxClamp := TRUE;\n~~~\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ST 代码块: 1" in result.stdout, result.stdout


def test_inline_fence_markers_do_not_change_block_boundaries():
    expect_valid("文中出现 ` ```st ` 只是行内标记。\n```st\nxClamp := TRUE;\n```\n")
    expect_valid("正文提到 ```st 而不是围栏，随后仍是正文。\n")


def test_quoted_st_fence_is_accepted_and_counted():
    result = run("> ```st\n> x := TRUE;\n> ```\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ST 代码块: 1" in result.stdout, result.stdout


def test_unclosed_quoted_st_fence_reports_opening_line():
    text = "> ```st\n> x := TRUE;\n"
    expect_invalid_at(text, 1)
    result = run(text)
    assert "ST 围栏未闭合" in result.stdout, result.stdout


def test_inline_quoted_fence_marker_is_not_an_error():
    expect_valid("> 引用里提到 ```st 但不是围栏。\n")


def test_invalid_indented_st_fence_has_line_diagnostic():
    expect_invalid_at("    ```st\nxClamp := TRUE;\n    ```\n", 1)


def test_joined_closing_fence_has_explicit_line_error():
    from markdown_fences import fence_diagnostics
    for marker in ('```', '~~~'):
        for tail in ('', '\n' + marker + '\n## 后续说明\n正文\n'):
            text = marker + 'st\nx := TRUE;' + marker + tail
            errors = fence_diagnostics(text)
            assert any('L2' in e and '闭合围栏必须独立一行' in e for e in errors), errors
            for script in ('validate_st_rendering.py', 'check_document_layout.py', 'check_markdown_format.py', 'validate_handbook.py', 'check_local_explanation.py'):
                if script == 'check_local_explanation.py':
                    with tempfile.TemporaryDirectory() as directory:
                        doc = Path(directory) / 'doc.md'
                        source = Path(directory) / 'source.st'
                        doc.write_text(text)
                        source.write_text('x := TRUE;\n')
                        result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts' / script),
                                                 str(doc), '--source', str(source)], capture_output=True, text=True)
                else:
                    result = run_script(ROOT / 'scripts' / script, text)
                assert result.returncode == 1 and '闭合围栏必须独立一行' in result.stdout, (script, result.stdout, result.stderr)


def test_valid_fence_indentation_and_string_literals_are_not_joined_closers():
    expect_valid('```st\nx := TRUE;\n  ```  \n')
    expect_valid("```st\ns := 'literal ```';\n```\n")


def main() -> int:
    tests = [test_format_checker_accepts_nested_short_fence_example,
             test_layout_checker_uses_matching_fence_character_and_length,
             test_code_extraction_preserves_inner_short_fence_as_st_source,
             test_screenshot_like_unclosed_st_has_opening_line_diagnostic,
             test_long_backtick_fence_can_contain_short_backtick_example,
             test_short_closer_does_not_close_long_opener,
             test_backtick_and_tilde_fences_pair_only_with_same_character,
             test_cross_character_line_does_not_close_st_fence,
             test_legal_st_block_is_recognized_and_accepted,
             test_inline_fence_markers_do_not_change_block_boundaries,
             test_quoted_st_fence_is_accepted_and_counted,
             test_unclosed_quoted_st_fence_reports_opening_line,
             test_inline_quoted_fence_marker_is_not_an_error,
             test_invalid_indented_st_fence_has_line_diagnostic,
             test_joined_closing_fence_has_explicit_line_error,
             test_valid_fence_indentation_and_string_literals_are_not_joined_closers]
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
