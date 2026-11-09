#!/usr/bin/env python3
"""内容一致性检查：术语叫法、步号、空白章节与重复段落。

用法：
  python3 scripts/check_content_consistency.py <文档.md> [--strict]

默认只报问题、退出码 0；--strict 时有问题即退出 1。
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path
from markdown_fences import parse_fences, body_view, fence_diagnostics

HEADING = re.compile(r"^(#{2,6})\s+(.+)$")
ALIAS = re.compile(r"`([A-Za-z_][\w.]*)`\s*[（(]\s*(?:简称|又称|也叫|别名|即)\s*[:：]?\s*([\u4e00-\u9fa5A-Za-z0-9]{2,16})\s*[）)]")
STEP_TEXT = re.compile(r"步\s*(\d{1,3})")
STEP_NODE = re.compile(r"步(\d{1,3})[_\u4e00-\u9fa5A-Za-z]")
MIN_PARA = 40


def terms(text: str) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """只认显式别名（简称/又称/也叫/别名/即），避免把括号注解误判成同义词。"""
    var2names: dict[str, set[str]] = defaultdict(set)
    name2vars: dict[str, set[str]] = defaultdict(set)
    for var, name in ALIAS.findall(text):
        var2names[var].add(name)
        name2vars[name].add(var)
    return var2names, name2vars


def steps(text: str) -> tuple[set[int], set[int]]:
    table: set[int] = set()
    body = body_view(text).split("\n")
    for i, ln in enumerate(body):
        if ln.strip().startswith("|") and "步" in ln and i + 1 < len(body) and set(ln) & set("-| "):
            if re.search(r"\|\s*步\s*\|", ln):
                j = i + 2
                while j < len(body) and body[j].strip().startswith("|"):
                    cell = body[j].strip().strip("|").split("|")[0].strip()
                    if cell.isdigit():
                        table.add(int(cell))
                    j += 1
    mermaid = "\n".join(block["text"] for block in parse_fences(text) if block["lang"] == "mermaid")
    figure_steps = {int(n) for n in STEP_NODE.findall(mermaid)} or {int(n) for n in STEP_TEXT.findall(mermaid)}
    return table, figure_steps


def structure_issues(lines: list[str]) -> list[str]:
    issues: list[str] = []
    for i, ln in enumerate(lines):
        m = HEADING.match(ln)
        if not m:
            continue
        level = len(m.group(1))
        j, content, child = i + 1, [], False
        while j < len(lines):
            nxt = HEADING.match(lines[j])
            if nxt:
                if len(nxt.group(1)) > level:
                    child = True
                break
            if lines[j].strip():
                content.append(lines[j].strip())
            j += 1
        if child:
            continue
        if not content:
            issues.append(f"第 {i + 1} 行章节为空：{m.group(2).strip()}")
        elif sum(len(c) for c in content) < 12:
            issues.append(f"第 {i + 1} 行章节内容过少：{m.group(2).strip()}")
    return issues


def duplicates(lines: list[str]) -> list[str]:
    seen: dict[str, int] = defaultdict(int)
    for ln in lines:
        s = ln.strip()
        if len(s) >= MIN_PARA and not s.startswith(("|", "#", "```", "<!--")):
            key = re.sub(r"[\s，。、；：（）()「」“”]", "", s)
            seen[key] += 1
    return [f"重复段落（出现 {n} 次）：{k[:30]}…" for k, n in seen.items() if n > 1]


def check(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    lines = body_view(text).splitlines()
    issues: list[str] = fence_diagnostics(text)

    var2names, name2vars = terms(body_view(text))
    for var, names in sorted(var2names.items()):
        if len(names) > 1:
            issues.append(f"同一变量出现多种叫法：`{var}` → " + "、".join(sorted(names)))
    for name, vars_ in sorted(name2vars.items()):
        if len(vars_) > 1:
            issues.append(f"同一叫法对应多个变量：{name} → " + "、".join(sorted(vars_)))

    table_steps, figure_steps = steps(text)
    if table_steps and figure_steps:
        extra = sorted(figure_steps - table_steps)
        missing = sorted(table_steps - figure_steps)
        if extra:
            issues.append("状态图出现表中没有的步：" + "、".join(f"步{s}" for s in extra))
        if missing:
            issues.append("步表中有图里缺失的步：" + "、".join(f"步{s}" for s in missing))

    issues.extend(structure_issues(lines))
    issues.extend(duplicates(lines))
    return issues


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("documents", nargs="+", type=Path)
    ap.add_argument("--strict", action="store_true", help="有提醒即返回 1")
    args = ap.parse_args(argv)

    total = 0
    for doc in args.documents:
        if not doc.is_file():
            print(f"ERROR 找不到文件：{doc}")
            total += 1
            continue
        issues = check(doc)
        print(f"一致性检查: {doc.name}  问题 {len(issues)}")
        for issue in issues:
            print(f"  - {issue}")
        total += len(issues)
    return 1 if (args.strict and total) else 0


if __name__ == "__main__":
    raise SystemExit(main())
