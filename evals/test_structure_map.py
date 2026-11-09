#!/usr/bin/env python3
"""结构梳理文档校验器的正反向回归。"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_structure_map.py"
SAMPLE = ROOT / "references" / "example-structure-map.md"


def run(doc: Path, *extra: str):
    return subprocess.run([sys.executable, "-B", str(SCRIPT), str(doc), *extra],
                          capture_output=True, text=True, cwd=ROOT, check=False)


def _mutated(old: str, new: str, count: int = 1) -> Path:
    text = SAMPLE.read_text(encoding="utf-8").replace(old, new, count)
    tmp = Path(tempfile.mkdtemp()) / "map.md"
    tmp.write_text(text, encoding="utf-8")
    return tmp


def test_sample_passes():
    r = run(SAMPLE)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "0 个错误" in r.stdout


def test_missing_chapter_fails():
    r = run(_mutated("## 八、阅读顺序", "## 八、删除的章节"))
    assert r.returncode == 1
    assert "缺少章节：## 八、阅读顺序" in r.stdout


def test_relation_table_requires_confidence_column():
    r = run(_mutated("| 证据 | 证据等级 |", "| 证据 | 备注 |"))
    assert r.returncode == 1
    assert "关系表缺少证据等级列" in r.stdout


def test_relation_table_rejects_noncanonical_evidence_level():
    r = run(_mutated("| 互锁 | 工位 1 / S02 | 工位 2 / S01 | `xClampDone` | 跨周期 | 加工无许可 | `export.txt:83` | 已确认 |",
                     "| 互锁 | 工位 1 / S02 | 工位 2 / S01 | `xClampDone` | 跨周期 | 加工无许可 | `export.txt:83` | 待验证 |"))
    assert r.returncode == 1
    assert "证据等级无效" in r.stdout


def test_final_rejects_unfinished_segment_status():
    doc = _mutated("| W01-S03 | 保压监视 | 监视 | 监视到位保持并计时 | `xClampDone` | `xClampAlarm` | 24–30 | 已讲 |",
                   "| W01-S03 | 保压监视 | 监视 | 监视到位保持并计时 | `xClampDone` | `xClampAlarm` | 24–30 | 待补资料 |")
    assert run(doc).returncode == 0, "中间稿应允许未完成状态"
    r = run(doc, "--final")
    assert r.returncode == 1
    assert "最终稿仍有未完成状态" in r.stdout


def main() -> int:
    tests = [test_sample_passes, test_missing_chapter_fails,
             test_relation_table_requires_confidence_column,
             test_relation_table_rejects_noncanonical_evidence_level,
             test_final_rejects_unfinished_segment_status]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as exc:
            failed += 1
            print(f"FAIL {t.__name__}: {exc}")
        else:
            print(f"PASS {t.__name__}")
    print(f"{len(tests) - failed}/{len(tests)} passed")
    return int(failed > 0)


if __name__ == "__main__":
    raise SystemExit(main())
