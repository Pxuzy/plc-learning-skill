#!/usr/bin/env python3
"""make_manifest.py 的正反例自测。"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _harness as harness  # noqa: E402

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SCRIPT = SKILL / "scripts" / "make_manifest.py"
CHECKER = SKILL / "scripts" / "check_code_integrity.py"

EXPORT = """// 导出文件头
// 工程：ST_T030
[MainProgram]
// NETWORK 1
IF xStart THEN
    yClamp := TRUE;
END_IF;

// NETWORK 2
IF xClampDone THEN
    yRun := TRUE;
END_IF;

// NETWORK 3
yRun := FALSE;
// 文件尾
"""


def run(src: str, *args: str) -> harness.Result:
    return harness.run(SCRIPT, src, *args)


def case_basic(tmp: Path) -> None:
    src = tmp / "export.txt"
    out = tmp / "manifest.json"
    src.write_text(EXPORT, encoding="utf-8")
    proc = run(str(src), "--out", str(out))
    assert proc.returncode == 0, proc.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["pattern"] == "network", data["pattern"]
    assert len(data["units"]) == 3, data["units"]
    assert data["source_lines"] == 16, data["source_lines"]
    assert data["units"][0]["id"] == "MainProgram.N1", data["units"][0]
    assert data["units"][0]["start"] == 4
    assert data["exclude"][0]["reason"] == "文件头"
    # 覆盖完整性：单元 + 排除 = 全部行
    covered = {ln for u in data["units"] for ln in range(u["start"], u["end"] + 1)}
    for e in data["exclude"]:
        covered |= set(range(e["start"], e["end"] + 1))
    assert covered == set(range(1, data["source_lines"] + 1)), sorted(set(range(1, 17)) - covered)


def case_duplicate(tmp: Path) -> None:
    src = tmp / "dup.txt"
    src.write_text("[POU]\n// NETWORK 1\na := 1;\n// NETWORK 1\nb := 2;\n", encoding="utf-8")
    proc = run(str(src), "--out", str(tmp / "m.json"))
    assert proc.returncode == 1, proc.stdout
    assert "id 重复" in proc.stderr, proc.stderr


def case_no_marker(tmp: Path) -> None:
    src = tmp / "plain.txt"
    src.write_text("just text\nnothing here\n", encoding="utf-8")
    proc = run(str(src), "--out", str(tmp / "m.json"))
    assert proc.returncode == 1, proc.stdout
    assert "未识别到程序单元" in proc.stderr, proc.stderr


def case_pou(tmp: Path) -> None:
    src = tmp / "pou.txt"
    src.write_text("[Main]\na := 1;\n\n[Sub]\nb := 2;\n", encoding="utf-8")
    out = tmp / "m.json"
    proc = run(str(src), "--out", str(out), "--pattern", "pou")
    assert proc.returncode == 0, proc.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert [u["id"] for u in data["units"]] == ["Main", "Sub"], data["units"]


def case_sha_mismatch(tmp: Path) -> None:
    src = tmp / "export.txt"
    out = tmp / "manifest.json"
    src.write_text(EXPORT, encoding="utf-8")
    assert run(str(src), "--out", str(out)).returncode == 0
    src.write_text(EXPORT.replace("yRun := FALSE;", "yRun := TRUE;"), encoding="utf-8")
    doc = tmp / "doc.md"
    doc.write_text("<!-- src: 4-16 -->\n```st\n" + EXPORT.splitlines()[3] + "\n```\n", encoding="utf-8")
    proc = harness.run(CHECKER, "--manifest", str(out), "--doc", str(doc))
    assert proc.returncode == 1, (proc.stdout, proc.stderr)
    assert "哈希" in proc.stdout + proc.stderr, proc.stdout + proc.stderr


def case_gap(tmp: Path) -> None:
    sys.path.insert(0, str(SKILL / "scripts"))
    import make_manifest as mm  # noqa: PLC0415

    units = [
        {"id": "A", "start": 1, "end": 2},
        {"id": "B", "start": 4, "end": 4},
    ]
    try:
        mm.validate_manifest(units, [], 4)
    except mm.ManifestError as exc:
        assert "缺口" in str(exc), exc
    else:
        raise AssertionError("缺口未被发现")


def case_pou_header_not_swallowed(tmp: Path) -> None:
    """最后一个网络不能把下一个 POU 头算进正文。"""
    src = tmp / "two_pou.txt"
    src.write_text(
        "[Main]\nNETWORK 10\na := 1;\n[FB_X]\nNETWORK 10\nb := 2;\n", encoding="utf-8"
    )
    out = tmp / "m.json"
    proc = run(str(src), "--out", str(out))
    assert proc.returncode == 0, proc.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    by_id = {u["id"]: u for u in data["units"]}
    assert by_id["Main.N10"]["end"] == 3, by_id["Main.N10"]
    assert by_id["FB_X.N10"]["start"] == 5, by_id["FB_X.N10"]
    # POU 头本身不属于任何单元，应进 exclude
    assert any(e["start"] == 4 and e["end"] == 4 for e in data["exclude"]), data["exclude"]
    assert {u["id"]: (u["start"], u["end"]) for u in data["units"]} == {
        "Main.N10": (2, 3),
        "FB_X.N10": (5, 6),
    }, data["units"]


def case_single_network_auto(tmp: Path) -> None:
    """单 POU 单 NETWORK 的导出应能被 auto 识别。"""
    src = tmp / "single.txt"
    src.write_text("[Main]\nNETWORK 1\na := 1;\n", encoding="utf-8")
    out = tmp / "m.json"
    proc = run(str(src), "--out", str(out))
    assert proc.returncode == 0, proc.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["pattern"] == "network", data["pattern"]
    assert [(u["id"], u["start"], u["end"]) for u in data["units"]] == [("Main.N1", 2, 3)], data["units"]


def case_single_network_multi_pou_ambiguous(tmp: Path) -> None:
    """单个 NETWORK 落在多个 POU 之间时，auto 不得猜归属。"""
    src = tmp / "ambiguous.txt"
    src.write_text("[Main]\nNETWORK 1\na := 1;\n[FB_X]\nb := 2;\n", encoding="utf-8")
    proc = run(str(src), "--out", str(tmp / "m.json"))
    assert proc.returncode == 1, proc.stdout
    assert "歧义" in proc.stderr, proc.stderr
    assert "--pattern" in proc.stderr, proc.stderr

    # 歧义只影响 auto；显式 pattern 仍然可用。
    out = tmp / "m2.json"
    proc = run(str(src), "--out", str(out), "--pattern", "pou")
    assert proc.returncode == 0, proc.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert [u["id"] for u in data["units"]] == ["Main", "FB_X"], data["units"]


def main() -> int:
    tests = [
        case_basic,
        case_duplicate,
        case_no_marker,
        case_pou,
        case_pou_header_not_swallowed,
        case_single_network_auto,
        case_single_network_multi_pou_ambiguous,
        case_sha_mismatch,
        case_gap,
    ]
    passed = 0
    for fn in tests:
        with tempfile.TemporaryDirectory() as td:
            try:
                fn(Path(td))
            except AssertionError as exc:
                print(f"FAIL {fn.__name__}: {exc}")
                continue
        passed += 1
        print(f"PASS {fn.__name__}")
    print(f"{passed}/{len(tests)} 通过")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())
