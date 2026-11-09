#!/usr/bin/env python3
"""模板注册表结构与组合关系的正反向回归。"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_template_index.py"
INDEX = ROOT / "references" / "template-index.md"


def run(text: str | None = None):
    if text is None:
        path = INDEX
    else:
        temp_dir = tempfile.TemporaryDirectory()
        path = Path(temp_dir.name) / "template-index.md"
        path.write_text(text, encoding="utf-8")
        try:
            return subprocess.run(
                [sys.executable, "-B", str(SCRIPT), str(path)],
                capture_output=True, text=True, cwd=ROOT, check=False,
            )
        finally:
            temp_dir.cleanup()
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPT), str(path)],
        capture_output=True, text=True, cwd=ROOT, check=False,
    )


def test_canonical_index_passes():
    result = run()
    assert result.returncode == 0, result.stdout + result.stderr


def test_duplicate_template_id_fails():
    text = INDEX.read_text(encoding="utf-8")
    row = "| FLOW | 3.0 | `references/process-and-signal-flow.md` | 可组合专题 | 请求工艺动作流程、信号链，或两者对照 | HBK, FB, ST, STATE, INTERFACE |"
    assert row in text
    text = text.replace(row, row + "\n" + row, 1)
    result = run(text)
    assert result.returncode == 1
    assert "模板 ID 重复" in result.stdout


def test_asymmetric_composition_fails():
    text = INDEX.read_text(encoding="utf-8")
    text = text.replace(
        "| HBK | 3.0 | `references/template-handbook.md` | 共享基底 | 需要交付项目手册或对象讲解文档 | FB, ST, STATE, INTERFACE, FLOW |",
        "| HBK | 3.0 | `references/template-handbook.md` | 共享基底 | 需要交付项目手册或对象讲解文档 | FB, ST, INTERFACE, FLOW |",
        1,
    )
    result = run(text)
    assert result.returncode == 1
    assert "组合关系不对称" in result.stdout


def test_template_without_route_fails():
    text = INDEX.read_text(encoding="utf-8")
    text = text.replace("| FLOW | 工艺动作、信号链或两者关系 |", "| FLOW-REMOVED | 工艺动作、信号链或两者关系 |", 1)
    result = run(text)
    assert result.returncode == 1
    assert "未登记路由" in result.stdout


def test_invalid_template_version_fails():
    text = INDEX.read_text(encoding="utf-8").replace("| FLOW | 3.0 |", "| FLOW | latest |", 1)
    result = run(text)
    assert result.returncode == 1
    assert "模板版本格式错误" in result.stdout


def test_duplicate_or_truncated_route_rows_fail():
    text = INDEX.read_text(encoding="utf-8")
    route = "| FLOW | 工艺动作、信号链或两者关系 | HBK + FLOW | 保留现有工艺/信号模板；不由代码推定机械事实 |"
    assert route in text
    duplicate = run(text.replace(route, route + "\n" + route, 1))
    assert duplicate.returncode == 1
    assert "路由 ID 重复" in duplicate.stdout
    truncated = run(text.replace(route, "| FLOW | 工艺动作、信号链或两者关系 | HBK + FLOW |", 1))
    assert truncated.returncode == 1
    assert "路由表列数错误" in truncated.stdout


def test_registry_template_id_must_match_file_declaration():
    text = INDEX.read_text(encoding="utf-8").replace(
        "| FLOW | 3.0 | `references/process-and-signal-flow.md` |",
        "| FLOW | 3.0 | `references/template-state-machine.md` |", 1)
    result = run(text)
    assert result.returncode == 1
    assert "模板文件自声明不匹配" in result.stdout


def main() -> int:
    tests = [
        test_canonical_index_passes,
        test_duplicate_template_id_fails,
        test_asymmetric_composition_fails,
        test_template_without_route_fails,
        test_invalid_template_version_fails,
        test_duplicate_or_truncated_route_rows_fail,
        test_registry_template_id_must_match_file_declaration,
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
