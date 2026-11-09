#!/usr/bin/env python3
"""Validate a generated PLC explanation handbook without echoing its contents."""

import argparse
from pathlib import Path
import re
import sys


SECTIONS = (
    "## 1. 功能定位与执行条件",
    "## 2. 源码",
    "## 3. 代码块整体讲解",
    "## 4. 形象示例",
    "## 5. 程序交互与段间交接",
)
FENCE = re.compile(r"```[^\r\n]*\r?\n(.*?)\r?\n```", re.S)


def canonical(value):
    """Normalize line endings while preserving source line content."""
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return value.strip("\n") + "\n"


def read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def validate(source, handbook):
    errors = []
    positions = [handbook.find(section) for section in SECTIONS]
    if any(position < 0 for position in positions):
        errors.append("section-missing")
    elif positions != sorted(positions):
        errors.append("section-order")

    if "| 变量 | 数据类型 | 方向 | 含义 | 谁写谁读 | 证据等级 |" not in handbook:
        errors.append("variable-table")

    review_position = handbook.find("## 批判性审查")
    verification_position = handbook.find("### 验证状态")
    if review_position < 0:
        errors.append("review-section")
    if verification_position < 0 or (review_position >= 0 and verification_position < review_position):
        errors.append("verification-section")

    if positions[1] >= 0 and positions[2] >= 0:
        source_section = handbook[positions[1]:positions[2]]
        blocks = [canonical(match) for match in FENCE.findall(source_section)]
        if not blocks:
            errors.append("source-block")
        elif canonical(source) not in blocks:
            errors.append("source-coverage")

    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate a PLC Markdown handbook.")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--handbook", required=True, type=Path)
    args = parser.parse_args(argv)

    source = read_text(args.source)
    handbook = read_text(args.handbook)
    errors = []
    if source is None:
        errors.append("source-read")
    if handbook is None:
        errors.append("handbook-read")
    if not errors:
        errors.extend(validate(source, handbook))

    if errors:
        print("Handbook validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Handbook validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
