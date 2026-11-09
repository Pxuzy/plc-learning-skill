#!/usr/bin/env python3
"""survey_program.py 自测：6 个用例。"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from survey_program import scan  # noqa: E402

EXPORT = """[MainProgram]
NETWORK 1
IF X0 THEN
    yRun := TRUE;
END_IF;

NETWORK 2
IF X1 THEN
    yRun := FALSE;
END_IF;

NETWORK 3
TON_1(IN := yRun, PT := T#2S);
dCount := D100 + 1;
Y0 := yRun;
"""


def write(text: str) -> Path:
    f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
    f.write(text)
    f.close()
    return Path(f.name)


def test_counts():
    data = scan(write(EXPORT), "auto", 12)
    assert data["units"] == 3, data["units"]
    assert data["pous"]["MainProgram"]["networks"] == 3


def test_cross_unit_write():
    data = scan(write(EXPORT), "auto", 12)
    assert "Y0" not in data["cross_unit_writes"]  # 只有 yRun 被两个网络写
    assert data["cross_unit_writes"]["YRUN"] == ["MainProgram.N1", "MainProgram.N2"]


def test_single_unit_write_not_flagged():
    data = scan(write(EXPORT), "auto", 12)
    assert "DCOUNT" not in data["cross_unit_writes"]


def test_addresses():
    data = scan(write(EXPORT), "auto", 12)
    prefixes = data["address_counts"]
    assert prefixes.get("X") == 2, prefixes
    assert prefixes.get("Y") == 1, prefixes
    assert prefixes.get("D") == 1, prefixes


def test_timers():
    data = scan(write(EXPORT), "auto", 12)
    assert data["timer_units"] == {"MainProgram.N3": 1}, data["timer_units"]


def test_section_pattern():
    text = "SECTION 初始化\nxInit := TRUE;\n\nSECTION 运行\nyRun := xInit;\n"
    data = scan(write(text), "section", 12)
    assert data["units"] == 2, data["units"]


def test_operator_is_not_a_call():
    text = "[MainProgram]\nNETWORK 1\nyOut := xLeft OR xRight;\nTON_1(IN := yOut);\n"
    data = scan(write(text), "auto", 12)
    assert "OR" not in data["calls"], data["calls"]
    assert data["timers"][0]["kind"] == "TON_1", data["timers"]


def test_call_positions_keep_single_letter_and_nested_operands():
    text = ('[MainProgram]\nNETWORK 1\nA();\n'
            'Result := Left COMBINE (Right);\n'
            'Result := Left COMBINE Check();\n'
            'Result := Check() COMBINE (Check());\n')
    data = scan(write(text), 'network', 12)
    assert data['calls'] == {'Check': 3, 'A': 1}, data['calls']


if __name__ == "__main__":
    failures = 0
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for name, fn in tests:
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} 通过")
    raise SystemExit(1 if failures else 0)
