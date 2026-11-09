#!/usr/bin/env python3
"""diff_export.py 自测：6 个用例。"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from diff_export import diff, snapshot  # noqa: E402

BASE = """[MainProgram]
NETWORK 1
IF X0 THEN
    yRun := TRUE;
END_IF;

NETWORK 2
IF X1 THEN
    yRun := FALSE;
END_IF;
"""

CHANGED = BASE.replace("yRun := FALSE;", "yRun := FALSE;\n    yAlarm := TRUE;")
ADDED = BASE + "\nNETWORK 3\nY0 := yRun;\n"
REMOVED = BASE.split("\nNETWORK 2")[0] + "\n"
SHIFTED = "\n\n" + BASE


def snap(text: str) -> dict:
    f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
    f.write(text)
    f.close()
    return snapshot(Path(f.name), "auto")


def test_identical():
    data = diff(snap(BASE), snap(BASE))
    assert not data["added"] and not data["removed"] and not data["modified"]


def test_modified():
    data = diff(snap(BASE), snap(CHANGED))
    assert [m["id"] for m in data["modified"]] == ["MainProgram.N2"], data["modified"]
    assert data["unchanged"] == ["MainProgram.N1"]


def test_added():
    data = diff(snap(BASE), snap(ADDED))
    assert [a["id"] for a in data["added"]] == ["MainProgram.N3"]


def test_removed():
    data = diff(snap(BASE), snap(REMOVED))
    assert [r["id"] for r in data["removed"]] == ["MainProgram.N2"]


def test_line_shift_is_not_change():
    data = diff(snap(BASE), snap(SHIFTED))
    assert not data["modified"], data["modified"]
    assert data["unchanged"] == ["MainProgram.N1", "MainProgram.N2"]


def test_new_pou_all_added():
    data = diff(snap(BASE), snap(BASE + "\n[Other]\nNETWORK 1\nx := TRUE;\n"))
    assert [a["id"] for a in data["added"]] == ["Other.N1"]


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    print(f"\n{6 - failures}/6 通过")
    raise SystemExit(1 if failures else 0)
