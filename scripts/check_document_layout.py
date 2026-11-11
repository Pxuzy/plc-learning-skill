#!/usr/bin/env python3
"""文档版式与可读性检查：目录顺序、标题命名、围栏、表格、段落长度。

用法：
  python3 scripts/check_document_layout.py <文档.md> [<文档2.md> ...]

退出码：0 通过；1 存在错误。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from markdown_fences import PLC_LANGS, parse_fences, body_view, fence_diagnostics

CN_NUM = "一二三四五六七八九十"
HEADING = re.compile(r"^(#{1,6})\s+(.+)$")
EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")
# 模块级标题：不绑定单一命名法，M01、B1、N1、步骤三 都算，防止换编号绕过表情门禁。
MODULE_HEAD = re.compile(r"^(?:[MBN]\d{1,3}|模块\s*\d+|步骤\s*[0-9一二三四五六七八九十]+)")
TABLE_ROW = re.compile(r"^\|.*\|\s*$")
SEPARATOR = re.compile(r"^\|[-:| ]+\|\s*$")
ALLOWED_LANGS = PLC_LANGS | {"text", "mermaid", "bash", "json", "markdown", ""}
BAD_HEADINGS = [r"^框架\s*\d*$", r"^程序段\s*[A-Za-z]*\d+$", r"^[Bb]0b\d+$", r"^obj\d+$"]
MAX_PARAGRAPH = 300
MAX_CODE_LINE = 140
MAX_TABLE_COLS = 8


def check(path: Path) -> tuple[list[str], list[str]]:
    text = path.read_text(encoding="utf-8")
    lines = body_view(text).splitlines()
    errors: list[str] = fence_diagnostics(text)
    from markdown_syntax import inspect_markdown
    try:
        errors.extend(f"L{x['line']} {x['rule']}: {x['detail']}" for x in
                      inspect_markdown(text, path, check_links=False)['issues'])
    except RuntimeError as exc:
        errors.append(str(exc))
    warnings: list[str] = []

    # Fence pairing and language labels use the shared CommonMark parser.
    for block in parse_fences(text):
        if block["lang"] not in ALLOWED_LANGS:
            warnings.append(f"第 {block['line']} 行代码围栏语言 `{block['lang']}` 不在推荐集合（pascal/st/text/mermaid）")
        if not block["closed"]:
            errors.append(f"第 {block['line']} 行代码围栏未闭合")
        for number, code_line in enumerate(block["source_lines"], block["line"] + 1):
            if len(code_line) > MAX_CODE_LINE:
                warnings.append(f"第 {number} 行代码超过 {MAX_CODE_LINE} 字符，建议折行或拆分")

    # 标题层级与命名
    prev_level = 0
    for i, ln in enumerate(lines, 1):
        m = HEADING.match(ln)
        if not m:
            continue
        level, title = len(m.group(1)), m.group(2).strip()
        if prev_level and level > prev_level + 1:
            errors.append(f"第 {i} 行标题层级跳跃：{prev_level} 级 → {level} 级（{title}）")
        prev_level = level
        for pattern in BAD_HEADINGS:
            if re.match(pattern, title):
                errors.append(f"第 {i} 行标题缺少语义：{title}（应为“M01 名称”这类）")
        if '讲解深度：' in text and not EMOJI.search(title):
            errors.append(f"第 {i} 行模块标题缺少表情：{title}（规则 PLC-TITLE-EMOJI）")

    # 章节编号连续性（## 一、二、…）
    nums = []
    for ln in lines:
        m = re.match(r"^##\s+([一二三四五六七八九十]+)、", ln)
        if m:
            token=m.group(1)
            if '十' in token:
                tens,units=token.split('十',1)
                if len(tens)>1 or len(units)>1:
                    errors.append(f"无法识别章节编号：{token}")
                    continue
                number=(CN_NUM.index(tens)+1 if tens else 1)*10+(CN_NUM.index(units)+1 if units else 0)
            elif len(token)==1:
                number=CN_NUM.index(token)+1
            else:
                errors.append(f"无法识别章节编号：{token}")
                continue
            nums.append(number)
    nums = [n for n in nums if n]
    for a, b in zip(nums, nums[1:]):
        if b <= a:
            errors.append(f"章节顺序错误：{a} → {b}（章节不得倒序或重复）")

    # 表格列数与列上限
    block: list[str] = []
    for ln in lines + [""]:
        if TABLE_ROW.match(ln.strip()):
            block.append(ln.strip())
            continue
        if block:
            from markdown_syntax import cells as table_cells
            cols = {len(table_cells(r)) for r in block if not SEPARATOR.match(r)}
            if len(cols) > 1:
                errors.append(f"同一表格列数不一致：{sorted(cols)}")
            widest = max(cols) if cols else 0
            if widest > MAX_TABLE_COLS:
                warnings.append(f"表格 {widest} 列，超过建议上限 {MAX_TABLE_COLS}")
            block = []

    # 段落长度
    para = ""
    for ln in lines + [""]:
        s = ln.strip()
        if not s or s.startswith(("|", "#", "```", "- ", "* ", ">", "<!--")):
            if len(para) > MAX_PARAGRAPH:
                warnings.append(f"段落超过 {MAX_PARAGRAPH} 字符，建议拆分：{para[:30]}…")
            para = ""
            continue
        para += s
    return errors, warnings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("documents", nargs="+", type=Path)
    args = ap.parse_args(argv)

    failed = False
    for doc in args.documents:
        if not doc.is_file():
            print(f"ERROR 找不到文件：{doc}")
            failed = True
            continue
        errors, warnings = check(doc)
        print(f"版式检查: {doc.name}  错误 {len(errors)}  警告 {len(warnings)}")
        for e in errors:
            print(f"  ERROR {e}")
        for w in warnings:
            print(f"  WARN {w}")
        failed = failed or bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
