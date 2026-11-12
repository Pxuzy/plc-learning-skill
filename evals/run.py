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
# evals/tests/ 是宿主集成与治理测试，需显式 `python3 -B -m unittest discover -s evals/tests -t .`。
SUBDIR_NOTE = "未包含 evals/tests/ 下的宿主集成测试；需要时单独 discover。"
DEFAULT_TIMEOUT = 600


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="只列出将运行的本地测试")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                    help=f"单个测试文件超时秒数（默认 {DEFAULT_TIMEOUT}）")
    args = ap.parse_args(argv)

    if args.dry_run:
        for test in TESTS:
            print(test.relative_to(SKILL_DIR))
        print(f"共 {len(TESTS)} 个本地测试文件；不会发起网络请求。")
        print(SUBDIR_NOTE)
        return 0

    failed = []
    for test in TESTS:
        print(f"=== {test.name} ===", flush=True)
        try:
            result = subprocess.run([sys.executable, "-B", str(test)], cwd=SKILL_DIR,
                                    check=False, timeout=args.timeout)
        except subprocess.TimeoutExpired:
            failed.append((test.name, f"timeout>{args.timeout}s"))
            print(f"TIMEOUT {test.name} 超过 {args.timeout}s", flush=True)
            continue
        if result.returncode:
            failed.append((test.name, result.returncode))

    if failed:
        for name, code in failed:
            print(f"FAIL {name}: exit={code}")
        return 1
    print(SUBDIR_NOTE)
    print(f"本地回归测试通过：{len(TESTS)} 个文件。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
