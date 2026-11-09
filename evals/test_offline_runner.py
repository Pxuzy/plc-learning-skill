#!/usr/bin/env python3
"""离线评估入口不得读取模型凭据或建立网络连接。"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "evals" / "run.py"


def test_dry_run_lists_local_tests():
    proc = subprocess.run(
        [sys.executable, "-B", str(RUNNER), "--dry-run"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "test_offline_runner.py" in proc.stdout, proc.stdout
    assert "网络请求" in proc.stdout, proc.stdout


def test_readme_documents_only_the_offline_runner():
    readme = (ROOT / "evals" / "README.md").read_text(encoding="utf-8")
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "evals/run.py --out" not in readme
    assert "evals/run.py --reps" not in readme
    assert "账号信息由 shell 先导出" not in readme
    assert "evals/run.py --dry-run" in readme
    assert "references/catalog.md" in skill
    catalog = (ROOT / "references" / "catalog.md").read_text(encoding="utf-8")
    assert "evals/test_offline_runner.py" in catalog


def test_catalog_registration_matches_discovered_test_files():
    catalog = (ROOT / "references" / "catalog.md").read_text(encoding="utf-8")
    discovered = {path.name for path in (ROOT / "evals").glob("test_*.py")}
    registered = {Path(path).name for path in __import__("re").findall(
        r"\| `(evals/test_[^`]+\.py)` \|", catalog)}
    assert discovered == registered, f"discovered-only={discovered-registered}, registered-only={registered-discovered}"


if __name__ == "__main__":
    test_dry_run_lists_local_tests()
    test_readme_documents_only_the_offline_runner()
    test_catalog_registration_matches_discovered_test_files()
    print("PASS test_dry_run_lists_local_tests")
    print("PASS test_readme_documents_only_the_offline_runner")
