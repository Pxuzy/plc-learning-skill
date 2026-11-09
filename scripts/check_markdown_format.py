#!/usr/bin/env python3
"""检查生成文档的 Markdown 格式（F1～F10）。

用法：
    python3 scripts/check_markdown_format.py <document.md>

只查格式，不判断 PLC 内容对不对。
退出码：0 通过（可有警告），1 有格式错误。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from markdown_fences import parse_fences, body_view, fence_diagnostics

MAX_COLS = 4  # 逐句解释表按规则不该出现；出现时超过 4 列判超宽，结构化表用下方 6/8 列阈值
MAX_LINE = 160
NUMBERED_H2 = re.compile(r"^##\s*([一二三四五六七八九十]+)、")
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def main() -> int:
    if len(sys.argv) != 2:
        print("用法：python3 scripts/check_markdown_format.py <document.md>")
        return 1
    path = Path(sys.argv[1]).resolve()
    if not path.is_file():
        print(f"ERROR 找不到文档：{path}")
        return 1

    text = path.read_text(encoding="utf-8")
    lines = body_view(text).splitlines()
    errors: list[str] = fence_diagnostics(text)
    warnings: list[str] = []

    # F1 元信息块
    head = "\n".join(lines[:30])
    if "工程：" not in head or not re.search(r"(?:讲解)?深度：", head):
        warnings.append("F1 文档头未发现元信息块（工程：… / 讲解深度：…）")

    # F2 标题层级不跳级
    prev_level = 0
    for i, line in enumerate(lines, 1):
        m = re.match(r"^(#{1,6})\s+", line)
        if not m:
            continue
        level = len(m.group(1))
        if prev_level and level > prev_level + 1:
            warnings.append(f"F2 第 {i} 行标题从 H{prev_level} 跳到 H{level}")
        prev_level = level

    # F3 code fence pairing + F9 language labels
    blocks = parse_fences(text)
    for block in blocks:
        if not block["closed"]:
            errors.append(f"F3 代码围栏未闭合（第 {block['line']} 行开始）")
    no_lang = sum(not block["lang"] for block in blocks)
    if no_lang:
        warnings.append(f"F9 有 {no_lang} 个代码块未标注语言（建议 st / text / mermaid）")

    # F10 重复章节编号
    nums = [m.group(1) for m in (NUMBERED_H2.match(l) for l in lines) if m]
    dup = {n for n in nums if nums.count(n) > 1}
    if dup:
        warnings.append(f"F10 章节编号重复：{'、'.join(sorted(dup))}")

    # F4/F5 表格列数
    table: list[tuple[int, list[str]]] = []

    def check_table(rows: list[tuple[int, list[str]]]) -> None:
        if not rows:
            return
        width = len(rows[0][1])
        for ln, cells in rows[1:]:
            if len(cells) != width:
                errors.append(f"F4 第 {ln} 行表格列数 {len(cells)} 与表头 {width} 不一致")
        header = "|".join(rows[0][1])
        prose = any(k in header for k in ("原始元素", "逐项", "它检查/执行什么"))
        inventory = any(k in header for k in ("程序单元", "段/范围", "工位"))
        limit = 8 if inventory else 6
        if prose and width > MAX_COLS:
            warnings.append(f"F5 第 {rows[0][0]} 行是逐句解释表（{width} 列），建议改成“逐句看”小段")
        elif width > limit:
            warnings.append(f"F5 第 {rows[0][0]} 行表格有 {width} 列（上限 {limit} 列，建议拆表）")

    for i, line in enumerate(lines, 1):
        if line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            table.append((i, cells))
        else:
            check_table(table)
            table = []
    check_table(table)

    # F6 空章节
    for i, line in enumerate(lines):
        if not line.startswith("## "):
            continue
        body = []
        for nxt in lines[i + 1 :]:
            if nxt.startswith("## "):
                break
            if nxt.strip():
                body.append(nxt.strip())
        if not body:
            warnings.append(f"F6 第 {i + 1} 行章节为空：{line[3:].strip()[:30]}")

    # F7 超长行
    long_lines = [(i, len(l)) for i, l in enumerate(lines, 1) if len(l) > MAX_LINE]
    if long_lines:
        sample = "、".join(str(i) for i, _ in long_lines[:3])
        warnings.append(f"F7 有 {len(long_lines)} 行超过 {MAX_LINE} 字符（第 {sample} 行）")

    # F8 本地链接
    for m in LINK.finditer(text):
        target = m.group(1).split("#")[0].strip()
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        if not (path.parent / target).exists():
            warnings.append(f"F8 链接目标不存在：{target}")

    print(f"format: {path.name}  lines: {len(lines)}")
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    if errors:
        print(f"\n失败：{len(errors)} 个错误，{len(warnings)} 个警告")
        return 1
    print(f"\n通过：0 个错误，{len(warnings)} 个警告")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
