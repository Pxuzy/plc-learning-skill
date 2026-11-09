#!/usr/bin/env python3
"""对比两版 PLC 导出文本，给出按单元（网络/段）的增删改清单。

用法：
    python3 -B scripts/diff_export.py old.txt new.txt
    python3 -B scripts/diff_export.py old.txt new.txt --json diff.json
    python3 -B scripts/diff_export.py old.txt new.txt --fail-on-change

单元键为 `<POU>.N<网络号>`（或 POU/段名）。只比较单元正文，行号变化不算修改。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from make_manifest import ManifestError, build_units, pick_pattern, read_source


def snapshot(path: Path, pattern: str) -> dict:
    lines, sha = read_source(path)
    chosen = pick_pattern(lines, pattern, min_hits=1)
    units = build_units(lines, chosen)
    body: dict[str, dict] = {}
    for unit in units:
        text = "\n".join(lines[unit["start"] - 1:unit["end"]]).rstrip()
        body[unit["id"]] = {
            "start": unit["start"],
            "end": unit["end"],
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "text": text,
        }
    return {"source": path.name, "sha256": sha, "lines": len(lines),
            "pattern": chosen, "units": body}


def diff(old: dict, new: dict) -> dict:
    old_ids, new_ids = set(old["units"]), set(new["units"])
    added = sorted(new_ids - old_ids)
    removed = sorted(old_ids - new_ids)
    modified = sorted(
        uid for uid in old_ids & new_ids
        if old["units"][uid]["sha256"] != new["units"][uid]["sha256"]
    )
    unchanged = sorted(old_ids & new_ids - set(modified))
    return {
        "old": {"source": old["source"], "sha256": old["sha256"], "units": len(old_ids)},
        "new": {"source": new["source"], "sha256": new["sha256"], "units": len(new_ids)},
        "added": [{"id": uid, "start": new["units"][uid]["start"],
                   "end": new["units"][uid]["end"]} for uid in added],
        "removed": [{"id": uid, "start": old["units"][uid]["start"],
                     "end": old["units"][uid]["end"]} for uid in removed],
        "modified": [{"id": uid,
                      "old": [old["units"][uid]["start"], old["units"][uid]["end"]],
                      "new": [new["units"][uid]["start"], new["units"][uid]["end"]]}
                     for uid in modified],
        "unchanged": sorted(set(unchanged)),
    }


def render(data: dict) -> str:
    out = [f"# 版本差异：{data['old']['source']} → {data['new']['source']}", ""]
    out.append(f"- 旧版：{data['old']['units']} 单元，`{data['old']['sha256'][:12]}`")
    out.append(f"- 新版：{data['new']['units']} 单元，`{data['new']['sha256'][:12]}`")
    out.append(f"- 新增 {len(data['added'])} / 删除 {len(data['removed'])} / "
               f"修改 {len(data['modified'])} / 未变 {len(data['unchanged'])}")
    out.append("")
    for title, key in (("新增", "added"), ("删除", "removed"), ("修改", "modified")):
        out.append(f"## {title}")
        out.append("")
        if not data[key]:
            out.append("无。")
        else:
            out.append("| 单元 | 位置 |")
            out.append("|---|---|")
            for item in data[key]:
                if key == "modified":
                    pos = f"L{item['old'][0]}-{item['old'][1]} → L{item['new'][0]}-{item['new'][1]}"
                else:
                    pos = f"L{item['start']}-{item['end']}"
                out.append(f"| {item['id']} | {pos} |")
        out.append("")
    out.append("## 未变单元")
    out.append("")
    out.append("、".join(data["unchanged"]) if data["unchanged"] else "无。")
    out.append("")
    out.append("> 未变单元不需要重讲；修改单元按新行号重建 `src` 标注，编号沿用旧台账，不重排。")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="对比两版 PLC 导出文本")
    ap.add_argument("old", type=Path)
    ap.add_argument("new", type=Path)
    ap.add_argument("--pattern", choices=["auto", "network", "section", "pou"], default="auto")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--fail-on-change", action="store_true")
    args = ap.parse_args(argv)

    try:
        data = diff(snapshot(args.old, args.pattern), snapshot(args.new, args.pattern))
    except (ManifestError, UnicodeDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(render(data), end="")
    if args.json:
        args.json.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    changed = bool(data["added"] or data["removed"] or data["modified"])
    return 1 if (args.fail_on_change and changed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
