#!/usr/bin/env python3
"""校验结构梳理文档：章节、索引表、关系证据与阅读路径。

用法：
  python3 scripts/validate_structure_map.py <结构梳理.md>
  python3 scripts/validate_structure_map.py <结构梳理.md> --final
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from markdown_fences import body_view, fence_diagnostics

REQUIRED = [
    "## 一、用途与阅读方式",
    "## 二、工程对象清单",
    "## 三、执行结构树",
    "## 四、工位索引",
    "## 五、段索引",
    "## 六、变量与写入点",
    "## 七、调用与互锁关系",
    "## 八、阅读顺序",
    "## 九、缺口与待确认",
]
FORBIDDEN = ["其余略", "其余从略", "略过", "未展开", "同上", "见前文"]
UNFINISHED = {"待补资料", "受保护", "未讲解"}
EVIDENCE_LEVELS = {"已确认", "推断", "未知", "不适用"}


def section(text: str, heading: str) -> str:
    if heading not in text:
        return ""
    body = text.split(heading, 1)[1]
    m = re.search(r"\n## ", body)
    return body[: m.start()] if m else body


def tables(block: str) -> list[list[str]]:
    rows = []
    for ln in block.splitlines():
        ln = ln.strip()
        if ln.startswith("|") and not re.fullmatch(r"\|[-:| ]+\|", ln):
            rows.append([c.strip() for c in ln.strip("|").split("|")])
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("document", type=Path)
    ap.add_argument("--final", action="store_true", help="最终稿：拒绝未完成覆盖状态")
    args = ap.parse_args(argv)

    if not args.document.is_file():
        print(f"ERROR 找不到文件：{args.document}")
        return 1
    raw = args.document.read_text(encoding="utf-8")
    text = body_view(raw)
    errors: list[str] = fence_diagnostics(raw)
    warnings: list[str] = []

    if "文档类型：structure-map" not in text:
        errors.append("缺少元信息：文档类型：structure-map")
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

    seg = tables(section(text, "## 五、段索引"))
    if len(seg) <= 1:
        errors.append("段索引为空")
    elif len(seg[0]) < 6:
        errors.append("段索引列不足：需包含段号、名称、类型、功能、输入/输出、证据范围")

    var = tables(section(text, "## 六、变量与写入点"))
    if len(var) <= 1:
        errors.append("变量与写入点表为空")
    else:
        head = "".join(var[0])
        if "写入" not in head or "读取" not in head:
            errors.append("变量表缺少写入点或读取点列")

    rel = tables(section(text, "## 七、调用与互锁关系"))
    if len(rel) <= 1:
        errors.append("调用与互锁关系表为空")
    else:
        head = "".join(rel[0])
        if "证据" not in head:
            errors.append("关系表缺少证据列")
        if "证据等级" not in head:
            errors.append("关系表缺少证据等级列")
        else:
            level_column = next((i for i, value in enumerate(rel[0]) if "证据等级" in value), -1)
            if level_column >= 0:
                for row_number, row in enumerate(rel[1:], 2):
                    if len(row) <= level_column or row[level_column] not in EVIDENCE_LEVELS:
                        errors.append(f"关系表第 {row_number} 行证据等级无效：仅允许已确认/推断/未知/不适用")

    path = tables(section(text, "## 八、阅读顺序"))
    if len(path) <= 2:
        errors.append("阅读顺序至少包含两行步骤")

    unfinished = set()
    for row in tables(section(text, "## 五、段索引"))[1:]:
        hit = {s for s in ("待补资料", "受保护", "未讲解", "预留") if s in row}
        if hit & UNFINISHED:
            unfinished |= hit & UNFINISHED
    if args.final and unfinished:
        errors.append("最终稿仍有未完成状态：" + "、".join(sorted(unfinished)))

    print(f"结构梳理: {args.document.name}  章节: {len(REQUIRED)} 项 段索引: {max(len(seg) - 1, 0)} 段 关系: {max(len(rel) - 1, 0)} 条")
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
