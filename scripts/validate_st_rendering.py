#!/usr/bin/env python3
"""Check ST Markdown fences for render-safe CommonMark boundaries.

Usage: python3 scripts/validate_st_rendering.py <document.md> [<document2.md> ...]
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from markdown_fences import ST_LANGS, parse_fences, fence_diagnostics


def check(path: Path) -> tuple[list[str], int]:
    raw = path.read_text(encoding="utf-8-sig")
    blocks = parse_fences(raw)
    st_blocks = [block for block in blocks if block["lang"] in ST_LANGS]
    errors = fence_diagnostics(raw, ST_LANGS)
    errors = [re.sub(r"^L(\d+) ", r"第 \1 行 ", message) for message in errors]
    errors = [message.replace("围栏未闭合", "ST 围栏未闭合") for message in errors]
    return errors, len(st_blocks)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("documents", nargs="+", type=Path)
    args = ap.parse_args(argv)
    failed = False
    for path in args.documents:
        if not path.is_file():
            print(f"ERROR 找不到文件：{path}")
            failed = True
            continue
        errors, count = check(path)
        print(f"ST 代码块: {count}  文档: {path.name}  错误: {len(errors)}")
        for error in errors:
            print(f"ERROR {error}")
        failed = failed or bool(errors)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
