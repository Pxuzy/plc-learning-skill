#!/usr/bin/env python3
"""一页总览校验器的正反向回归。"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_overview.py"
SAMPLE = ROOT / "references" / "example-overview.md"


def run(doc: Path):
    return subprocess.run([sys.executable, "-B", str(SCRIPT), str(doc)],
                          capture_output=True, text=True, cwd=ROOT, check=False)


def _mutated(old: str, new: str) -> Path:
    text = SAMPLE.read_text(encoding="utf-8").replace(old, new, 1)
    tmp = Path(tempfile.mkdtemp()) / "overview.md"
    tmp.write_text(text, encoding="utf-8")
    return tmp


def test_sample_passes():
    r = run(SAMPLE)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "0 个错误" in r.stdout


def test_missing_reading_order_fails():
    r = run(_mutated("## 阅读顺序", "## 删掉的章节"))
    assert r.returncode == 1
    assert "缺少章节：## 阅读顺序" in r.stdout


def test_oversized_overview_fails():
    filler = "\n".join(f"- 细节条目 {i}：用于触发超限检测的冗长内容。" for i in range(120))
    r = run(_mutated("## 分册索引", filler + "\n\n## 分册索引"))
    assert r.returncode == 1
    assert "超出篇幅上限" in r.stdout or "超出字数上限" in r.stdout


def test_index_without_markdown_fails():
    text = SAMPLE.read_text(encoding="utf-8")
    start = text.index("## 分册索引")
    text = text[:start] + "## 分册索引\n\n| 文件 | 内容 | 状态 |\n|---|---|---|\n| 结构 | 对象清单 | 已生成 |\n"
    tmp = Path(tempfile.mkdtemp()) / "overview.md"
    tmp.write_text(text, encoding="utf-8")
    r = run(tmp)
    assert r.returncode == 1
    assert "未列出任何 .md 文件" in r.stdout


def main() -> int:
    tests = [test_sample_passes, test_missing_reading_order_fails,
             test_oversized_overview_fails, test_index_without_markdown_fails]
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
