#!/usr/bin/env python3
"""版式与可读性检查的正反向回归。"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_document_layout.py"
SAMPLES = [ROOT / "references" / "example-handbook.md",
           ROOT / "references" / "example-structure-map.md",
           ROOT / "references" / "example-overview.md"]


def run(*docs: Path):
    return subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, docs)],
                          capture_output=True, text=True, cwd=ROOT, check=False)


def _variant(old: str, new: str, count: int = 1) -> Path:
    text = SAMPLES[0].read_text(encoding="utf-8").replace(old, new, count)
    tmp = Path(tempfile.mkdtemp()) / "doc.md"
    tmp.write_text(text, encoding="utf-8")
    return tmp


def test_samples_pass():
    r = run(*SAMPLES)
    assert r.returncode == 0, r.stdout
    assert "错误 0" in r.stdout


def test_unclosed_fence_fails():
    text = SAMPLES[0].read_text(encoding="utf-8") + "\n```\n"
    tmp = Path(tempfile.mkdtemp()) / "doc.md"
    tmp.write_text(text, encoding="utf-8")
    r = run(tmp)
    assert r.returncode == 1
    assert "代码围栏未闭合" in r.stdout


def test_heading_level_jump_fails():
    doc = _variant("#### M02 夹紧控制", "###### M02 夹紧控制")
    r = run(doc)
    assert r.returncode == 1
    assert "标题层级跳跃" in r.stdout


def test_meaningless_heading_fails():
    doc = _variant("#### M02 夹紧控制", "#### 框架 2")
    r = run(doc)
    assert r.returncode == 1
    assert "标题缺少语义" in r.stdout


def test_uneven_table_fails():
    doc = _variant("| 场景 | 初始状态 | 输入序列与扫描过程 | 预期结果与依据 |",
                   "| 场景 | 条件 | 过程 |")
    r = run(doc)
    assert r.returncode == 1
    assert "列数不一致" in r.stdout


def test_chapter_order_reversal_and_duplicate_fail_but_gaps_pass():
    ordered = SAMPLES[0].read_text(encoding="utf-8")
    gap = re.sub(r"(?ms)^<a id=\"ch6\"></a>\n## 六、.*?(?=^<a id=\"ch7\"></a>)", "", ordered)
    gap_path = Path(tempfile.mkdtemp()) / "gap.md"
    gap_path.write_text(gap, encoding="utf-8")
    assert run(gap_path).returncode == 0
    reversed_doc = ordered.replace("## 一、", "## TEMP、", 1).replace("## 二、", "## 一、", 1).replace("## TEMP、", "## 二、", 1)
    reverse_path = Path(tempfile.mkdtemp()) / "reverse.md"
    reverse_path.write_text(reversed_doc, encoding="utf-8")
    result = run(reverse_path)
    assert result.returncode == 1
    assert "章节顺序错误" in result.stdout
    duplicate_doc = ordered.replace("## 二、执行框架", "## 一、工程与边界", 1)
    duplicate_path = Path(tempfile.mkdtemp()) / "duplicate.md"
    duplicate_path.write_text(duplicate_doc, encoding="utf-8")
    result = run(duplicate_path)
    assert result.returncode == 1
    assert "章节顺序错误" in result.stdout


def main() -> int:
    tests = [test_samples_pass, test_unclosed_fence_fails, test_heading_level_jump_fails,
             test_meaningless_heading_fails, test_uneven_table_fails,
             test_chapter_order_reversal_and_duplicate_fail_but_gaps_pass]
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
