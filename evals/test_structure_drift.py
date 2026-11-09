#!/usr/bin/env python3
"""结构漂移检查：只报差异、不改文件。"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_structure_drift.py"

DOC_TMPL = """# 结构梳理

> `source_sha256`：{sha}

## 五、段索引

| 段号 | 名称 | 类型 | 功能定义 | 输入 | 输出 | 行/网络 | 状态 |
|---|---|---|---|---|---|---|---|
| P1.N1 | 映射 | 映射 | 输入映射 | X0 | xPartIn | 1–4 | 已讲 |
| P1.N2 | 夹紧 | 自动 | 夹紧控制 | iStep | yValve | 5–9 | 已讲 |
"""


def setup(units, sha="aabbccdd1122", doc_sha=None):
    tmp = Path(tempfile.mkdtemp())
    doc = tmp / "10-结构.md"
    doc.write_text(DOC_TMPL.format(sha=doc_sha or sha), encoding="utf-8")
    man = tmp / "manifest.json"
    man.write_text(json.dumps({
        "source": "export.txt",
        "source_sha256": sha,
        "units": [{"id": u} for u in units],
    }, ensure_ascii=False), encoding="utf-8")
    return doc, man


def run(doc: Path, man: Path):
    return subprocess.run([sys.executable, "-B", str(SCRIPT), "--doc", str(doc), "--manifest", str(man)],
                          capture_output=True, text=True, cwd=ROOT, check=False)


def test_no_drift():
    doc, man = setup(["P1.N1", "P1.N2"])
    before = doc.read_text(encoding="utf-8")
    r = run(doc, man)
    assert r.returncode == 0, r.stdout
    assert "无漂移" in r.stdout
    assert doc.read_text(encoding="utf-8") == before, "检查过程不得修改文档"


def test_sha_mismatch_reports_drift():
    doc, man = setup(["P1.N1", "P1.N2"], sha="aabbccdd1122", doc_sha="ffee99887766")
    r = run(doc, man)
    assert r.returncode == 1
    assert "摘要不符" in r.stdout


def test_added_unit_reports_drift():
    doc, man = setup(["P1.N1", "P1.N2", "P1.N3"])
    r = run(doc, man)
    assert r.returncode == 1
    assert "+ P1.N3" in r.stdout
    assert "源中新增" in r.stdout


def test_removed_unit_reports_drift():
    doc, man = setup(["P1.N1"])
    r = run(doc, man)
    assert r.returncode == 1
    assert "- P1.N2" in r.stdout


def main() -> int:
    tests = [test_no_drift, test_sha_mismatch_reports_drift,
             test_added_unit_reports_drift, test_removed_unit_reports_drift]
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
