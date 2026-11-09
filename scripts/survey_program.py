#!/usr/bin/env python3
"""全貌扫描：在逐段讲解之前，先给出程序的结构、地址与写入点候选。

用法：
    python3 -B scripts/survey_program.py export.txt
    python3 -B scripts/survey_program.py export.txt --json survey.json
    python3 -B scripts/survey_program.py export.txt --max-addresses 20

输出是候选统计，不是已确认事实；词法遮罩排除注释与字符串，未覆盖语法须人工核对。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from make_manifest import PATTERNS, ManifestError, build_units, pick_pattern, read_source
from check_plc_comments import lex_lines

ADDRESS = re.compile(
    r"(?<![\w.])("
    r"%[IQM][XBWDL]?\d+(?:\.\d+)?"
    r"|\b(?:CIO|DM|EM|HR|AR|IR)\d+(?:\.\d+)?"
    r"|\b(?:X|Y|W|H|D|A|E)\d+(?:\.\d+)?"
    r")(?![\w.])",
    re.IGNORECASE,
)
ASSIGN = re.compile(r"(?<![\w.])([%A-Za-z_][\w.%\[\]]*)\s*:=\s*\S")
OUT_CALL = re.compile(r"\b(?:SET|RSET|OUT)\s*\(\s*([^,()]+?)\s*[,)]", re.IGNORECASE)
CALL = re.compile(r"\b([A-Za-z_]\w*(?:\s*\.\s*[A-Za-z_]\w*)*)\s*\(")
EXPRESSION_TOKEN = re.compile(r'[A-Za-z_]\w*(?:\s*\.\s*[A-Za-z_]\w*)*|\d+(?:\.\d+)?|:=|=>|[^\s]')
TIMER = re.compile(r"\b((?:TON|TOF|TP|TIMX?|CTU|CTD|CTUD|CNT|TM)[A-Za-z0-9_]*)\s*\(", re.IGNORECASE)
KEYWORDS = {
    "if", "then", "else", "elsif", "end_if", "case", "of", "end_case", "for", "to", "by",
    "do", "end_for", "while", "end_while", "repeat", "until", "end_repeat", "return",
    "and", "or", "not", "mod", "true", "false", "function", "program", "end_program",
}


def unit_lines(lines: list[str], unit: dict) -> list[str]:
    return lines[unit["start"] - 1:unit["end"]]


def call_candidates(line: str):
    """Word operators occupy an infix slot; names in operand slots may call."""
    candidates = {m.start(): m for m in CALL.finditer(line)}
    needs_operand = True
    for token in EXPRESSION_TOKEN.finditer(line):
        value = re.sub(r'\s+', '', token.group())
        if re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*', value):
            if value.lower() in KEYWORDS:
                needs_operand = value.lower() not in {'true', 'false'}
            elif needs_operand:
                if token.start() in candidates:
                    yield candidates[token.start()]
                needs_operand = False
            else:
                needs_operand = True
        elif value in {')', ']'} or value[0].isdigit():
            needs_operand = False
        else:
            needs_operand = True


def scan(path: Path, pattern: str, max_addresses: int) -> dict:
    lines, sha = read_source(path)
    lexical, lexical_errors = lex_lines("\n".join(lines))
    masked_lines = [line["mask"] for line in lexical]
    # Export markers written as // NETWORK/SECTION are metadata outside block
    # comments; identical text inside a block comment must not create a unit.
    structure_lines = [original if not lex["block_comment_at_start"]
                       and any(PATTERNS[k].search(original) for k in ("network", "section"))
                       else lex["mask"] for original, lex in zip(lines, lexical)]
    chosen = pick_pattern(structure_lines, pattern, min_hits=1)
    units = build_units(structure_lines, chosen)

    addresses: dict[str, set[str]] = defaultdict(set)
    writes: dict[str, set[str]] = defaultdict(set)
    write_sites: list[dict] = []
    timers: list[dict] = []
    calls: Counter[str] = Counter()

    for unit in units:
        body = unit_lines(masked_lines, unit)
        for offset, line in enumerate(body):
            for match in ADDRESS.finditer(line):
                token = match.group(1)
                prefix = re.match(r"[%A-Za-z]+", token).group(0).upper()
                addresses[prefix].add(token.upper())

            targets = [assign.group(1) for assign in ASSIGN.finditer(line)]
            for call in OUT_CALL.finditer(line):
                targets.append(call.group(1).strip())
            for target in targets:
                key = target.upper()
                writes[key].add(unit["id"])
                write_sites.append(
                    {"target": target, "unit": unit["id"], "line": unit["start"] + offset}
                )

            for call in call_candidates(line):
                name = call.group(1)
                if name.lower() not in KEYWORDS:
                    calls[name] += 1

            for timer in TIMER.finditer(line):
                timers.append({"kind": timer.group(1).upper(), "unit": unit["id"],
                               "line": unit["start"] + offset})

    pous: dict[str, dict] = {}
    for unit in units:
        entry = pous.setdefault(unit["pou"], {"networks": 0, "lines": 0})
        entry["networks"] += 1
        entry["lines"] += unit["end"] - unit["start"] + 1

    cross_unit = {
        target: sorted(owners)
        for target, owners in writes.items()
        if len(owners) > 1
    }
    return {
        "classification": "候选统计",
        "syntax_limits": ["仅识别文本中的直接 := 与 SET/RSET/OUT 调用；支持基本同行 IF 和多语句",
                          "不解析完整 IEC 语法、作用域、别名、任务调度与实际执行条件",
                          "间接寻址、指针、动态下标、图形网络和外部/HMI 写入可能漏计",
                          "声明初始化可能算作写入候选，须与周期执行写入区分",
                          "定时器只按调用名称前缀列候选；任意实例名须回查声明类型，未列出不代表不存在"],
        "lexical_errors": lexical_errors,
        "source": path.name,
        "source_sha256": sha,
        "source_lines": len(lines),
        "pattern": chosen,
        "units": len(units),
        "pous": pous,
        "addresses": {k: sorted(v) for k, v in sorted(addresses.items())},
        "address_counts": {k: len(v) for k, v in addresses.items()},
        "writes": {k: len(v) for k, v in writes.items()},
        "cross_unit_writes": cross_unit,
        "write_sites": write_sites,
        "timers": timers,
        "timer_units": dict(Counter(t["unit"] for t in timers)),
        "calls": dict(calls.most_common(20)),
    }


def render(data: dict, max_addresses: int) -> str:
    out: list[str] = []
    out.append(f"# 程序全貌扫描（候选统计）：{data['source']}")
    out.append("")
    out.append(f"- 源行：{data['source_lines']}；单元：{data['units']}；切分：`{data['pattern']}`")
    out.append(f"- 源哈希：`{data['source_sha256'][:12]}`")
    out.append("")
    out.append("## POU 分布")
    out.append("")
    out.append("| POU | 网络/段 | 行数 |")
    out.append("|---|---|---|")
    for name, stat in data["pous"].items():
        out.append(f"| {name} | {stat['networks']} | {stat['lines']} |")
    out.append("")
    out.append("## 地址候选")
    out.append("")
    out.append("| 前缀 | 数量 | 示例 |")
    out.append("|---|---|---|")
    for prefix, count in sorted(data["address_counts"].items(), key=lambda kv: -kv[1]):
        sample = "、".join(data["addresses"][prefix][:max_addresses])
        out.append(f"| {prefix} | {count} | {sample} |")
    out.append("")
    out.append("> 地址只按字面提取；具体含义必须来自符号表或变量注释，未见符号表时标 `推断`。")
    out.append("")
    out.append("## 跨单元重复写入（扫描顺序风险候选）")
    out.append("")
    if data["cross_unit_writes"]:
        out.append("| 目标 | 写入单元 |")
        out.append("|---|---|")
        for target, owners in sorted(data["cross_unit_writes"].items())[:30]:
            out.append(f"| {target} | {'、'.join(owners)} |")
        out.append("")
        out.append("> 重复写入不等于双线圈错误：可能是置位/复位配对、手动/自动两路、或不同模式分支。必须回到代码确认执行顺序。")
    else:
        out.append("未发现跨单元重复写入。单单元内多次写入仍可能互相覆盖，见 `write_sites`。")
    out.append("")
    out.append("## 定时器/计数器")
    out.append("")
    if data["timers"]:
        out.append("| 类型 | 数量 | 涉及单元 |")
        out.append("|---|---|---|")
        kinds = Counter(t["kind"] for t in data["timers"])
        for kind, count in kinds.most_common():
            owners = sorted({t["unit"] for t in data["timers"] if t["kind"] == kind})
            out.append(f"| {kind} | {count} | {'、'.join(owners[:8])} |")
        out.append("")
        out.append("> 要检查实例是否复用、时基与设定值单位；同一个 TON 实例被两处调用会互相覆盖。")
    else:
        out.append("未发现常见定时器/计数器调用。")
    out.append("")
    out.append("## 调用候选（出现次数）")
    out.append("")
    if data["calls"]:
        out.append("、".join(f"`{name}`×{count}" for name, count in data["calls"].items()))
    else:
        out.append("未识别到函数/FB 调用。")
    out.append("")
    out.append("## 扫描局限")
    out.append("")
    out.append("- LAD/FBD 导出若没有文本指令，写入点会漏；只按本文件可见内容计数。")
    out.append("- 间接寻址、数组下标、指针、HMI 写入不在统计内。")
    out.extend("- " + item for item in data["syntax_limits"])
    out.extend("- 词法诊断：" + item for item in data["lexical_errors"])
    out.append("- 本扫描不判断对错，候选需回到原始来源确认。")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="扫描 PLC 导出文本，产出全貌候选统计")
    ap.add_argument("source", type=Path)
    ap.add_argument("--pattern", choices=["auto", "network", "section", "pou"], default="auto")
    ap.add_argument("--json", type=Path, help="同时写出 JSON")
    ap.add_argument("--max-addresses", type=int, default=12)
    args = ap.parse_args(argv)

    try:
        data = scan(args.source, args.pattern, args.max_addresses)
    except (ManifestError, UnicodeDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(render(data, args.max_addresses), end="")
    if args.json:
        args.json.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
