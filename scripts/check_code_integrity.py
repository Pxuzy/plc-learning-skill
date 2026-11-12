#!/usr/bin/env python3
"""校验文档中的 PLC 代码块与源程序逐行一致：不缺失、不重复、不改写、不编造。

用法：
    python3 scripts/check_code_integrity.py --manifest manifest.json --doc 文档.md
    python3 scripts/check_code_integrity.py --manifest manifest.json --doc 文档.md --strict --json
    python3 scripts/check_code_integrity.py --manifest manifest.json --doc 文档.md --only-units P1.N10,P1.N20
    python3 scripts/check_code_integrity.py --manifest manifest.json --doc 文档.md --final

清单格式（manifest.json）：
{
  "source": "export.txt",
  "exclude": [{"start": 1, "end": 4, "reason": "文件头"}],
  "units": [
    {"id": "P1.N10", "pou": "MainProgram", "kind": "network", "start": 10, "end": 24}
  ]
}

文档标注：代码围栏前一行写 <!-- src: 10-24 -->（同一源文件）或 <!-- src: export.txt:10-24 -->。
代码块内的行必须与源行逐字一致；允许在行尾追加 " // 中文说明"（--strict 禁止）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_plc_comments import PLC_LANGS, fences

from source_annotations import source_annotation

CHECK_LANGS = PLC_LANGS


def norm(line: str) -> str:
    return line


def compress(nums: list[int]) -> str:
    if not nums:
        return "无"
    nums = sorted(nums)
    out, start, prev = [], nums[0], nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
            continue
        out.append(f"L{start}" if start == prev else f"L{start}-L{prev}")
        start = prev = n
    out.append(f"L{start}" if start == prev else f"L{start}-L{prev}")
    return "、".join(out)


class Report:
    def __init__(self) -> None:
        self.missing: list[str] = []
        self.duplicate: list[str] = []
        self.extra: list[str] = []
        self.altered: list[str] = []
        self.truncated: list[str] = []
        self.meta: list[str] = []
        self.allowed: list[str] = []
        self.pseudo: list[str] = []
        self.appended = 0
        self.blocks = 0
        self.covered_lines = 0
        self.total_lines = 0
        self.excluded_lines = 0
        self.units = 0
        self.scope = "全部单元"
        self.protected_units: list[str] = []
        self.protected_lines = 0

    @property
    def errors(self) -> int:
        return len(self.missing) + len(self.duplicate) + len(self.extra) + len(self.altered) + len(self.truncated) + len(self.meta)


def load_manifest(path: Path) -> tuple[Path, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    src = Path(data["source"])
    if not src.is_absolute():
        src = path.parent / src
    if not src.exists():
        raise SystemExit(f"源文件不存在：{src}")
    expected = data.get("source_sha256")
    if expected:
        actual = hashlib.sha256(src.read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit(
                f"清单与源文件版本不一致（哈希不符）：清单 {expected[:12]}… 实际 {actual[:12]}…，"
                "请重新运行 make_manifest.py"
            )
    return src, data


def check_manifest(source: list[str], data: dict, rep: Report) -> dict[int, str]:
    total = len(source)
    rep.total_lines = total
    excluded: set[int] = set()
    for e in data.get("exclude", []):
        s, t = int(e["start"]), int(e["end"])
        if s < 1 or t > total or s > t:
            rep.meta.append(f"排除区间越界：L{s}-L{t}")
            continue
        excluded.update(range(s, t + 1))
    rep.excluded_lines = len(excluded)

    owner: dict[int, str] = {}
    units = data.get("units", [])
    rep.units = len(units)
    ids = set()
    for u in units:
        uid = str(u.get("id", "")).strip()
        if not uid:
            rep.meta.append("清单单元缺少 id")
            continue
        if uid in ids:
            rep.duplicate.append(f"清单 id 重复：{uid}")
        ids.add(uid)
        s, t = int(u.get("start", 0)), int(u.get("end", 0))
        if s < 1 or t > total or s > t:
            rep.meta.append(f"{uid} 范围越界：L{s}-L{t}")
            continue
        for ln in range(s, t + 1):
            if ln in excluded:
                rep.meta.append(f"{uid} 覆盖了排除行 L{ln}")
            if ln in owner:
                rep.duplicate.append(f"源行重复归属：L{ln} 同属 {owner[ln]} 与 {uid}")
            owner[ln] = uid
        if u.get("protected") is True:
            rep.protected_units.append(uid)
            rep.protected_lines += t - s + 1

    missing = [ln for ln in range(1, total + 1) if ln not in owner and ln not in excluded]
    if missing:
        rep.missing.append(f"清单未覆盖：{compress(missing)}")
    return owner


def parse_doc(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8")
    blocks = []
    for block in fences(raw):
        ann = source_annotation(raw, block)
        blocks.append({**block, "annotation": ann, "none": bool(ann and ann.group("none"))})
    return blocks


def compare(src_lines: list[str], doc_lines: list[str], strict: bool) -> tuple[str, list[str], int]:
    """返回 (状态, 差异说明, 追加注释行数)。状态：ok / truncated / altered。"""
    if len(doc_lines) < len(src_lines) and doc_lines == src_lines[: len(doc_lines)]:
        return "truncated", [], 0
    if len(doc_lines) != len(src_lines):
        return "altered", [f"行数不符：源 {len(src_lines)} 行，文档 {len(doc_lines)} 行"], 0
    appended, diffs = 0, []
    for n, (a, b) in enumerate(zip(src_lines, doc_lines), 1):
        if a == b:
            continue
        if not strict and a.strip() and b.startswith(a) and re.match(r"^\s*//", b[len(a):]):
            appended += 1
            continue
        diffs.append(f"第 {n} 行：源「{a}」≠ 文档「{b}」")
    return ("ok" if not diffs else "altered"), diffs[:5], appended


def scope_manifest(data: dict, only_units: set[str], rep: Report) -> dict:
    """Limit coverage accounting to the selected object or batch."""
    units = [u for u in data.get("units", []) if str(u.get("id", "")) in only_units]
    known = {str(u.get("id", "")) for u in data.get("units", [])}
    unknown = sorted(only_units - known)
    if unknown:
        rep.meta.append(f"范围单元不存在：{', '.join(unknown)}")
    excluded = list(data.get("exclude", []))
    for unit in data.get("units", []):
        if str(unit.get("id", "")) not in only_units:
            excluded.append({"start": int(unit["start"]), "end": int(unit["end"]), "reason": "范围外单元"})
    scoped = dict(data)
    scoped["units"] = units
    scoped["exclude"] = excluded
    return scoped


def run(
    manifest_path: Path,
    doc_path: Path,
    strict: bool,
    allow_uncovered: set[str],
    only_units: set[str] | None = None,
    final: bool = False,
) -> Report:
    src, data = load_manifest(manifest_path)
    source = src.read_text(encoding="utf-8", errors="replace").splitlines()
    rep = Report()
    if only_units:
        rep.scope = ",".join(sorted(only_units))
        data = scope_manifest(data, only_units, rep)
    owner = check_manifest(source, data, rep)
    units = {str(u["id"]): u for u in data.get("units", []) if u.get("id")}

    blocks = parse_doc(doc_path)
    doc_owner: dict[int, int] = {}
    covered_by_unit: dict[str, set[int]] = {uid: set() for uid in units}
    previous_range: tuple[int, int] | None = None

    for b in blocks:
        if b["lang"] not in CHECK_LANGS:
            continue
        if not b["closed"]:
            rep.meta.append(f"第 {b['line']} 行：PLC 代码围栏未闭合")
        if b["none"]:
            rep.pseudo.append(f"第 {b['line']} 行：标记为伪代码，未参与比对")
            continue
        ann = b["annotation"]
        if not ann:
            rep.extra.append(f"第 {b['line']} 行：{b['lang']} 代码块没有 src 标注（未归属）")
            continue
        rep.blocks += 1
        start, end = int(ann.group("start")), int(ann.group("end"))
        fname = ann.group("file")
        if fname and Path(fname).name != src.name:
            rep.extra.append(f"第 {b['line']} 行：标注源文件 {fname} 与清单 {src.name} 不符")
            continue
        if start < 1 or end > len(source) or start > end:
            rep.extra.append(f"第 {b['line']} 行：标注范围 L{start}-L{end} 越界")
            continue
        if previous_range is not None and start <= previous_range[1]:
            rep.meta.append(
                f"第 {b['line']} 行：源码顺序错误：L{start}-L{end} 出现在 L{previous_range[0]}-L{previous_range[1]} 之后；代码块须按源行递增"
            )
        previous_range = (start, end)
        for ln in range(start, end + 1):
            if ln in doc_owner:
                rep.duplicate.append(f"L{ln} 被第 {doc_owner[ln]} 行与第 {b['line']} 行重复引用")
            doc_owner[ln] = b["line"]
        span_units = {owner[ln] for ln in range(start, end + 1) if ln in owner}
        if len(span_units) > 1:
            rep.meta.append(f"第 {b['line']} 行：代码块跨了多个单元 {sorted(span_units)}")
        for ln in range(start, end + 1):
            if ln in owner:
                covered_by_unit[owner[ln]].add(ln)
            else:
                rep.extra.append(f"第 {b['line']} 行：代码块引用清单外或排除的源行 L{ln}")

        src_lines = [norm(x) for x in source[start - 1 : end]]
        doc_lines = [norm(x) for x in b["source_lines"]]
        status, diffs, appended = compare(src_lines, doc_lines, strict)
        rep.appended += appended
        if status == "truncated":
            rep.truncated.append(
                f"第 {b['line']} 行（L{start}-L{end}）：只贴了前 {len(doc_lines)} 行，缺 {len(src_lines) - len(doc_lines)} 行"
            )
        elif status == "altered":
            rep.altered.append(f"第 {b['line']} 行（L{start}-L{end}）：" + "；".join(diffs))

    rep.covered_lines = len(doc_owner)
    for uid, u in units.items():
        need = set(range(int(u["start"]), int(u["end"]) + 1))
        have = covered_by_unit.get(uid, set())
        miss = sorted(need - have)
        if miss:
            if uid in allow_uncovered:
                rep.allowed.append(f"{uid} 按参数允许未覆盖：{compress(miss)}")
            else:
                rep.missing.append(f"{uid} 未覆盖或缺失：{compress(miss)}")
    if final and rep.pseudo:
        rep.meta.append("最终完整性校验含 src:none 伪代码块，不能声称逐行保真")
    if final and rep.allowed:
        rep.meta.append("最终完整性校验仍有允许未覆盖单元，不能标记完整")
    if final and rep.protected_units:
        rep.meta.append("最终完整性校验包含受保护单元，须标记为部分覆盖")
    return rep


def main() -> int:
    ap = argparse.ArgumentParser(description="PLC 文档代码完整性校验")
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--doc", required=True, type=Path)
    ap.add_argument("--strict", action="store_true", help="禁止行尾追加中文注释")
    ap.add_argument("--allow-uncovered", default="", help="允许未覆盖的单元 id，逗号分隔")
    ap.add_argument("--only-units", default="", help="只检查当前对象/批次的单元 id，逗号分隔")
    ap.add_argument("--final", action="store_true", help="最终报告门禁：拒绝伪代码、允许未覆盖和受保护单元")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    allow = {x.strip() for x in args.allow_uncovered.split(",") if x.strip()}
    only_units = {x.strip() for x in args.only_units.split(",") if x.strip()}
    rep = run(args.manifest, args.doc, args.strict, allow, only_units or None, args.final)
    ok = rep.errors == 0

    if args.json:
        print(
            json.dumps(
                {
                    "ok": ok,
                    "units": rep.units,
                    "blocks": rep.blocks,
                    "covered_lines": rep.covered_lines,
                    "total_lines": rep.total_lines,
                    "excluded_lines": rep.excluded_lines,
                    "appended_comments": rep.appended,
                    "missing": rep.missing,
                    "duplicate": rep.duplicate,
                    "extra": rep.extra,
                    "altered": rep.altered,
                    "truncated": rep.truncated,
                    "meta": rep.meta,
                    "allowed_uncovered": rep.allowed,
                    "pseudo": rep.pseudo,
                    "scope": rep.scope,
                    "protected_units": rep.protected_units,
                    "protected_lines": rep.protected_lines,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if ok else 1

    print(f"校验范围：{rep.scope}")
    print(f"源行：{rep.total_lines}（排除 {rep.excluded_lines}）  清单单元：{rep.units}  文档代码块：{rep.blocks}")
    print(f"覆盖源行：{rep.covered_lines}/{rep.total_lines - rep.excluded_lines}  行尾追加注释：{rep.appended} 行")
    print(f"受保护单元：{len(rep.protected_units)}（{rep.protected_lines} 行，单列不计为已验证）")
    labels = [
        ("缺失", rep.missing),
        ("重复", rep.duplicate),
        ("多余", rep.extra),
        ("改写", rep.altered),
        ("截断", rep.truncated),
        ("清单问题", rep.meta),
        ("允许未覆盖", rep.allowed),
    ]
    for name, items in labels:
        print(f"{name}：{len(items)}")
        for it in items[:20]:
            print(f"  - {it}")
    if rep.pseudo:
        print(f"伪代码块：{len(rep.pseudo)}（不参与比对）")
    print("通过" if ok else "不通过：除“允许未覆盖”外，六类问题必须为零")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
