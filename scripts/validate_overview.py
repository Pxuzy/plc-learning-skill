#!/usr/bin/env python3
"""校验一页总览：限一屏、必备六块、分册可追溯。

用法：
  python3 scripts/validate_overview.py 00-总览.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from markdown_fences import body_view, fence_diagnostics

REQUIRED = ["## 一句话", "## 对象计数", "## 主干", "## 阅读顺序", "## 未知与缺口", "## 分册索引"]
MAX_CHARS = 3000
MAX_LINES = 70
FORBIDDEN = ["其余略", "其余从略", "略过", "未展开", "同上", "见前文"]


def section(text: str, heading: str) -> str:
    if heading not in text:
        return ""
    body = text.split(heading, 1)[1]
    m = re.search(r"\n## ", body)
    return body[: m.start()] if m else body


def rows(block: str) -> list[list[str]]:
    out = []
    for ln in block.splitlines():
        ln = ln.strip()
        if ln.startswith("|") and not re.fullmatch(r"\|[-:| ]+\|", ln):
            out.append([c.strip() for c in ln.strip("|").split("|")])
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("document", type=Path)
    args = ap.parse_args(argv)
    if not args.document.is_file():
        print(f"ERROR 找不到文件：{args.document}")
        return 1

    raw = args.document.read_text(encoding="utf-8")
    text = body_view(raw)
    errors: list[str] = fence_diagnostics(raw)
    warnings: list[str] = []

    if "文档类型：overview" not in text:
        errors.append("缺少元信息：文档类型：overview")
    if "source_sha256" not in text:
        warnings.append("未记录 source_sha256，无法检测结构漂移")

    for heading in REQUIRED:
        if heading not in text:
            errors.append(f"缺少章节：{heading}")
        elif not section(text, heading).strip():
            errors.append(f"章节为空：{heading}")

    for phrase in FORBIDDEN:
        if phrase in text:
            errors.append(f"出现禁止省略用语：{phrase}")

    chars = len(text)
    lines = len(text.splitlines())
    if chars > MAX_CHARS:
        errors.append(f"总览超出字数上限：{chars} > {MAX_CHARS}（细节应移到结构分册）")
    if lines > MAX_LINES:
        errors.append(f"总览超出篇幅上限：{lines} 行 > {MAX_LINES} 行")

    order = rows(section(text, "## 阅读顺序"))
    if len(order) <= 2:
        errors.append("阅读顺序至少需要两步")
    elif "先看" not in "".join(order[0]):
        warnings.append("阅读顺序表建议包含“先看哪个变量”列")

    index = rows(section(text, "## 分册索引"))
    if len(index) <= 1:
        errors.append("分册索引为空")
    elif not any(".md" in cell for row in index[1:] for cell in row):
        errors.append("分册索引未列出任何 .md 文件")

    print(f"总览: {args.document.name}  字符: {chars}/{MAX_CHARS}  行: {lines}/{MAX_LINES}  分册: {max(len(index) - 1, 0)}")
    for w in warnings:
        print(f"WARN {w}")
    for e in errors:
        print(f"ERROR {e}")
    if errors:
        print(f"\n失败：{len(errors)} 个错误，{len(warnings)} 个警告")
        return 1
    print(f"\n通过：0 个错误，{len(warnings)} 个警告")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
