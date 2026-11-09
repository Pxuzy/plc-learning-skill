#!/usr/bin/env python3
"""内容一致性检查（术语 / 步号 / 空章节 / 重复段落）的正反向回归。"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_content_consistency.py"
SAMPLE = ROOT / "references" / "example-handbook.md"


def run(doc: Path, *extra: str):
    return subprocess.run([sys.executable, "-B", str(SCRIPT), str(doc), *extra],
                          capture_output=True, text=True, cwd=ROOT, check=False)


def _variant(*pairs: tuple[str, str]) -> Path:
    text = SAMPLE.read_text(encoding="utf-8")
    for old, new in pairs:
        text = text.replace(old, new, 1)
    tmp = Path(tempfile.mkdtemp()) / "doc.md"
    tmp.write_text(text, encoding="utf-8")
    return tmp


def test_sample_clean():
    r = run(SAMPLE)
    assert r.returncode == 0, r.stdout
    assert "问题 0" in r.stdout


def _standalone(body: str) -> Path:
    tmp = Path(tempfile.mkdtemp()) / "doc.md"
    tmp.write_text(body, encoding="utf-8")
    return tmp


def test_alias_drift_detected():
    doc = _standalone("- 输入：`xPartIn`（简称：入料信号）\n- 说明：`xPartIn`（又称：上料到位）\n")
    r = run(doc)
    assert "多种叫法" in r.stdout, r.stdout


def test_step_mismatch_detected():
    doc = _variant(("    步90_报警 --> 步10_等待上料: 手动复位", "    步90_报警 --> 步40_回原点: 手动复位"))
    r = run(doc)
    assert "状态图出现表中没有的步" in r.stdout
    assert "步40" in r.stdout


def test_empty_chapter_detected():
    doc = _variant(("## 九、未确认与证据 ❓", "## 八半、空章 🧪\n\n## 九、未确认与证据 ❓"))
    r = run(doc)
    assert "章节为空" in r.stdout


def test_duplicate_paragraph_detected():
    para = "该模块在自动模式下依据步号与到位反馈推进，复位由报警模块统一处理，因此输出责任单一，便于排查。"
    doc = _standalone(f"{para}\n\n{para}\n")
    r = run(doc)
    assert "重复段落" in r.stdout, r.stdout


def test_strict_exit_code():
    doc = _variant(("    步90_报警 --> 步10_等待上料: 手动复位", "    步90_报警 --> 步40_回原点: 手动复位"))
    assert run(doc).returncode == 0
    assert run(doc, "--strict").returncode == 1


def main() -> int:
    tests = [test_sample_clean, test_alias_drift_detected, test_step_mismatch_detected,
             test_empty_chapter_detected, test_duplicate_paragraph_detected, test_strict_exit_code]
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
