#!/usr/bin/env python3
"""运行技能自带的本地回归测试；不调用模型、不访问网络。"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
TESTS = sorted(HERE.glob("test_*.py"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="只列出将运行的本地测试")
    args = ap.parse_args(argv)

    if args.dry_run:
        for test in TESTS:
            print(test.relative_to(SKILL_DIR))
        print(f"共 {len(TESTS)} 个本地测试文件；不会发起网络请求。")
        return 0

    failed = []
    for test in TESTS:
        print(f"=== {test.name} ===", flush=True)
        result = subprocess.run([sys.executable, "-B", str(test)], cwd=SKILL_DIR, check=False)
        if result.returncode:
            failed.append((test.name, result.returncode))

    if failed:
        for name, code in failed:
            print(f"FAIL {name}: exit={code}")
        return 1
    print(f"本地回归测试通过：{len(TESTS)} 个文件。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
