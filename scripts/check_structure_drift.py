#!/usr/bin/env python3
"""结构漂移检查：只比对、只报告，不修改任何文件。

用法：
  python3 scripts/check_structure_drift.py --doc 10-结构.md --manifest manifest.json

退出码：0 无漂移；1 存在漂移或输入不可用。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from markdown_fences import body_view, fence_diagnostics

SHA_RE = re.compile(r"source_sha256`?\s*[:：]\s*`?([0-9a-fA-F]{6,}|[^\s|`]{2,})")


def doc_sha(text: str) -> str | None:
    m = SHA_RE.search(text)
    return m.group(1) if m else None


def doc_units(text: str) -> set[str]:
    if "## 五、段索引" not in text:
        return set()
    body = text.split("## 五、段索引", 1)[1]
    m = re.search(r"\n## ", body)
    if m:
        body = body[: m.start()]
    ids: set[str] = set()
    for ln in body.splitlines():
        ln = ln.strip()
        if not ln.startswith("|") or re.fullmatch(r"\|[-:| ]+\|", ln):
            continue
        first = ln.strip("|").split("|")[0].strip().strip("`")
        if first and first not in {"段号", ""}:
            ids.add(first)
    return ids


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--doc", type=Path, required=True, help="结构文档")
    ap.add_argument("--manifest", type=Path, required=True, help="make_manifest.py 生成的 manifest.json")
    args = ap.parse_args(argv)

    if not args.doc.is_file():
        print(f"ERROR 找不到结构文档：{args.doc}")
        return 1
    if not args.manifest.is_file():
        print(f"ERROR 找不到 manifest：{args.manifest}")
        return 1

    raw = args.doc.read_text(encoding="utf-8")
    text = body_view(raw)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR manifest 不是合法 JSON：{exc}")
        return 1

    src_sha = manifest.get("source_sha256", "")
    units_src = {u.get("id", "") for u in manifest.get("units", []) if u.get("id")}
    units_doc = doc_units(text)
    sha_doc = doc_sha(text)

    drift: list[str] = fence_diagnostics(raw)
    if not units_doc:
        drift.append("结构文档没有可解析的段索引，无法比对")
    if not units_src:
        drift.append("manifest 没有 units，无法比对")
    if sha_doc and src_sha and sha_doc != src_sha:
        drift.append(f"摘要不符：文档 {sha_doc[:12]} ≠ 源 {src_sha[:12]}")
    if not sha_doc:
        drift.append("结构文档未记录 source_sha256")

    added = sorted(units_src - units_doc)
    removed = sorted(units_doc - units_src)
    unchanged = sorted(units_src & units_doc)

    print(f"结构文档: {args.doc.name}  源: {manifest.get('source', '?')}")
    print(f"段数：文档 {len(units_doc)} / 源 {len(units_src)}")
    print(f"未变: {len(unchanged)}")
    if added:
        print("源中新增、文档未覆盖:")
        for u in added[:20]:
            print(f"  + {u}")
        drift.append(f"{len(added)} 个段在源中新增")
    if removed:
        print("文档中残留、源中已无:")
        for u in removed[:20]:
            print(f"  - {u}")
        drift.append(f"{len(removed)} 个段在源中已删除")

    if drift:
        print("\n漂移结论：存在漂移")
        for d in drift:
            print(f"  - {d}")
        print("本次未修改任何文件；请按差异更新结构文档后重跑。")
        return 1

    print("\n漂移结论：无漂移")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
