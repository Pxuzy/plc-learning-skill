#!/usr/bin/env python3
"""从 PLC 导出文本生成 check_code_integrity.py 可用的 manifest。

用法：
    python3 scripts/make_manifest.py export.txt --out manifest.json
    python3 scripts/make_manifest.py export.txt --out manifest.json --pattern network
    python3 scripts/make_manifest.py export.txt --out manifest.json --dry-run

识别规则（--pattern auto 时）：
    network  ^\\s*(?://\\s*)?NETWORK\\s*(\\d+)             欧姆龙 ST 导出
    section  ^\\s*(?://\\s*)?SECTION\\s*[:：]?\\s*(.*)$    结构化文本分段
    pou      ^\\[(?P<name>[A-Za-z_][\\w .-]*)\\]\\s*$       程序单元头

auto 优先选命中数最多的一种；只有单个 NETWORK 标记时也接受，但若同时
存在多个 POU，单网络无法唯一归属，会报歧义并提示改用 --pattern。

清单生成后立即自检：单元不得重叠、不得留缺口、id 不得重复。
仅空行、整行 // 注释及 [POU] 工程头可自动排除；未知前缀保留为待分类单元。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PATTERNS = {
    "network": re.compile(r"^\s*(?://\s*)?NETWORK\s*(\d+)\b", re.IGNORECASE),
    "section": re.compile(r"^\s*(?://\s*)?SECTION\s*[:：]?\s*(.*)$", re.IGNORECASE),
    "pou": re.compile(r"^\[([A-Za-z_][\w .-]*)\]\s*$"),
}
POU_DECL = re.compile(r"^\s*(?:PROGRAM|FUNCTION_BLOCK|FUNCTION)\s+([A-Za-z_][\w]*)\b", re.IGNORECASE)
MAX_PREVIEW = 40


class ManifestError(Exception):
    pass


def read_source(path: Path) -> tuple[list[str], str]:
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines, hashlib.sha256(raw).hexdigest()


def pou_headers(lines: list[str]) -> list[str]:
    names: list[str] = []
    for line in lines:
        match = PATTERNS["pou"].search(line) or POU_DECL.search(line)
        if match:
            names.append(match.group(1).strip())
    return names


def pick_pattern(lines: list[str], requested: str, min_hits: int = 2) -> str:
    if requested != "auto":
        return requested
    counts = {name: sum(1 for ln in lines if rx.search(ln)) for name, rx in PATTERNS.items()}
    pous = pou_headers(lines)
    if counts["network"] == 1 and len(set(pous)) > 1:
        raise ManifestError(
            "auto 识别歧义：只有 1 个 NETWORK 标记，却存在多个 POU（"
            + "、".join(sorted(set(pous))[:5])
            + "）；单网络无法唯一归属，请用 --pattern 明确指定"
        )
    strong = {name: count for name, count in counts.items() if count >= min_hits}
    if strong:
        return max(strong, key=lambda name: strong[name])
    if counts["network"] == 1:
        return "network"
    raise ManifestError(
        "未识别到程序单元：network/section/pou 的命中数分别为 "
        + "、".join(f"{k}={v}" for k, v in counts.items())
    )


def marker_name(pattern: str, line: str) -> str:
    if pattern == "network":
        return f"network {PATTERNS['network'].search(line).group(1)}"
    if pattern == "section":
        return PATTERNS["section"].search(line).group(1).strip() or "section"
    return PATTERNS["pou"].search(line).group(1).strip()


def current_pou(lines: list[str], upto: int) -> str:
    """向上找最近的 POU 声明，用于给 network 单元归属。"""
    for i in range(upto, -1, -1):
        m = PATTERNS["pou"].search(lines[i]) or POU_DECL.search(lines[i])
        if m:
            return m.group(1).strip()
    return "POU"


def build_units(lines: list[str], pattern: str) -> list[dict]:
    hits = [i for i, ln in enumerate(lines) if PATTERNS[pattern].search(ln)]
    if not hits:
        raise ManifestError(f"未找到 {pattern} 标记")
    units: list[dict] = []
    seen: set[str] = set()
    for idx, start0 in enumerate(hits):
        end0 = (hits[idx + 1] - 1) if idx + 1 < len(hits) else len(lines) - 1
        # 单元不得吞掉紧随其后的 POU 头（如 [FB_Clamp]），否则最后一个网络
        # 会把下一个程序块的头算进自己的正文，导致引用与差异比对失真。
        while end0 > start0 and (
            not lines[end0].strip() or (pattern != "pou" and PATTERNS["pou"].search(lines[end0]))
        ):
            end0 -= 1
        uid = marker_name(pattern, lines[start0])
        if pattern == "network":
            uid = f"{current_pou(lines, start0)}.N{uid.split()[-1]}"
        if uid in seen:
            raise ManifestError(f"单元 id 重复：{uid}（源行 L{start0 + 1}）")
        seen.add(uid)
        units.append(
            {
                "id": uid,
                "pou": current_pou(lines, start0) if pattern != "pou" else uid,
                "kind": pattern,
                "name": marker_name(pattern, lines[start0]),
                "start": start0 + 1,
                "end": end0 + 1,
            }
        )
    # Preserve declarations, initialization and unknown text outside markers.
    covered = {n for unit in units for n in range(unit["start"], unit["end"] + 1)}
    uncovered = [n for n in range(1, len(lines) + 1) if n not in covered]
    runs = []
    for n in uncovered:
        if runs and runs[-1][-1] == n - 1:
            runs[-1].append(n)
        else:
            runs.append([n])
    for run in runs:
        pending = [n for n in run if not metadata_line(lines[n - 1])]
        if pending:
            start, end = pending[0], pending[-1]
            units.append({"id": f"unclassified.L{start}", "pou": current_pou(lines, start - 1),
                          "kind": "unclassified", "name": "待分类源码", "start": start, "end": end})
    return sorted(units, key=lambda unit: unit["start"])


def metadata_line(line: str) -> bool:
    """Conservative allowlist; unknown header formats require human classification."""
    return not line.strip() or line.lstrip().startswith("//") or bool(PATTERNS["pou"].fullmatch(line))


def build_excludes(lines: list[str], units: list[dict]) -> list[dict]:
    covered = {ln for u in units for ln in range(u["start"], u["end"] + 1)}
    excludes: list[dict] = []
    run: list[int] = []

    def flush() -> None:
        if not run:
            return
        reason = "文件头" if run[0] == 1 else ("文件尾" if run[-1] == len(lines) else "单元间空行")
        excludes.append({"start": run[0], "end": run[-1], "reason": reason})
        run.clear()

    for ln in range(1, len(lines) + 1):
        if ln in covered:
            flush()
        else:
            if not metadata_line(lines[ln - 1]):
                raise ManifestError(f"L{ln} 不是可自动排除的工程头，须保留为待分类源码")
            run.append(ln)
    flush()
    return excludes


def validate_manifest(units: list[dict], excludes: list[dict], total: int) -> None:
    owner: dict[int, str] = {}
    for e in excludes:
        for ln in range(e["start"], e["end"] + 1):
            if ln in owner:
                raise ManifestError(f"L{ln} 同时被排除和被单元覆盖")
            owner[ln] = "exclude"
    for u in units:
        if u["start"] < 1 or u["end"] > total or u["start"] > u["end"]:
            raise ManifestError(f"{u['id']} 范围越界：L{u['start']}-L{u['end']}")
        for ln in range(u["start"], u["end"] + 1):
            if ln in owner:
                raise ManifestError(f"L{ln} 重复归属（{owner[ln]} / {u['id']}）")
            owner[ln] = u["id"]
    gaps = [ln for ln in range(1, total + 1) if ln not in owner]
    if gaps:
        head = "、".join(f"L{n}" for n in gaps[:MAX_PREVIEW])
        raise ManifestError(f"清单存在缺口：{head}" + ("…" if len(gaps) > MAX_PREVIEW else ""))


def make_manifest(path: Path, pattern: str) -> dict:
    lines, sha = read_source(path)
    chosen = pick_pattern(lines, pattern)
    units = build_units(lines, chosen)
    excludes = build_excludes(lines, units)
    validate_manifest(units, excludes, len(lines))
    return {
        "source": path.name,
        "source_sha256": sha,
        "source_lines": len(lines),
        "pattern": chosen,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "units": units,
        "exclude": excludes,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="从 PLC 导出文本生成 manifest.json")
    ap.add_argument("source", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--pattern", choices=["auto", "network", "section", "pou"], default="auto")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    try:
        manifest = make_manifest(args.source, args.pattern)
    except ManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except UnicodeDecodeError as exc:
        print(f"error: 源文件不是 UTF-8 文本（{exc}）", file=sys.stderr)
        return 1

    payload = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    if not args.dry_run:
        args.out.write_text(payload, encoding="utf-8")
    print(
        f"ok: {len(manifest['units'])} units / {manifest['source_lines']} lines / "
        f"{len(manifest['exclude'])} excludes / pattern={manifest['pattern']} / "
        f"sha256={manifest['source_sha256'][:12]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
