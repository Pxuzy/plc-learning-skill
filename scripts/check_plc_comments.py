#!/usr/bin/env python3
"""Check every PLC teaching fence for comment coverage and known low-value forms.

This is a lexical gate, not an IEC compiler or a semantic judge. A final claim
also requires an author review bound to the current document and each block.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from markdown_fences import PLC_LANGS, ST_LANGS, parse_fences, fence_diagnostics

CLOSE = re.compile(
    r"^(?:(?:END_(?:IF|FOR|CASE|WHILE|REPEAT|VAR|FUNCTION_BLOCK|FUNCTION|PROGRAM|"
    r"TYPE|STRUCT|METHOD|ACTION|PROPERTY|TRANSITION|CONFIGURATION|RESOURCE))\b\s*;?|[);\s])+$",
    re.I,
)
BOUNDARY = re.compile(r";|\b(?:THEN|DO|OF|ELSE)\b", re.I)
SYNTAX_ONLY = {
    "语句", "变量赋值", "把右边赋给左边", "将右侧赋给左侧", "条件成立进入分支",
    "条件成立时才执行", "条件成立时执行", "条件成立执行", "结束判断", "结束循环",
    "闭合分支", "条件判断开始", "循环开始", "把请求复制到使能变量", "输出置TRUE",
    "执行当前操作", "处理本段逻辑", "执行该分支", "进入分支", "否则以上条件均不成立时执行",
    "条件判断", "判断条件", "条件成立", "赋值", "置位", "复位", "调用", "初始化", "处理",
    "判断", "计算", "输出", "输入", "结束", "开始", "循环", "分支", "执行",
}
SYNTAX_PREFIXES = ("条件判断开始", "循环开始", "执行当前操作", "处理本段逻辑", "条件成立执行")
FIELD_TRANSLATION = re.compile(
    r"^(?:(?:将|把|给)\s*)?`?[\w.\[\]]+`?\s*(?:赋值为|设为|置为|设置为|复制为|等于|变为|写成|写入|赋值|置|写|赋|为)\s*"
    r"`?(?:TRUE|FALSE|真|假|[+-]?\d+(?:\.\d+)?)`?$", re.I,
)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fences(raw: str) -> list[dict]:
    """Compatibility wrapper around the shared CommonMark fence parser."""
    return parse_fences(raw)


def fence_errors(raw: str, blocks: list[dict]) -> list[str]:
    return fence_diagnostics(raw)


def lex_lines(text: str) -> tuple[list[dict], list[str]]:
    """Mask comments/literal contents without changing positions or source text.

    IEC $ escapes, doubled quotes and common vendor backslash escapes are
    recognized in either quote style. Block comments can be nested/multiline;
    only comments opened and closed after code on this line cover that line.
    """
    result, errors = [], []
    depth = 0
    for number, line in enumerate(text.splitlines(), 1):
        block_comment_at_start = bool(depth)
        masked = [" "] * len(line)
        comments = []
        quote = None
        start = None
        eligible = False
        i = 0
        while i < len(line):
            pair = line[i:i + 2]
            if depth:
                if pair == "(*":
                    depth += 1
                    i += 2
                elif pair == "*)":
                    depth -= 1
                    i += 2
                    if depth == 0 and start is not None and eligible:
                        comments.append((start, line[start + 2:i - 2]))
                else:
                    i += 1
                continue
            char = line[i]
            if quote:
                masked[i] = "x"
                if char in ("$", "\\") and i + 1 < len(line):
                    masked[i + 1] = "x"
                    i += 2
                    continue
                if char == quote:
                    if i + 1 < len(line) and line[i + 1] == quote:
                        masked[i + 1] = "x"
                        i += 2
                        continue
                    quote = None
                i += 1
                continue
            if char in ("'", '"'):
                quote = char
                masked[i] = "x"
            elif pair == "//":
                if "".join(masked).strip():
                    comments.append((i, line[i + 2:]))
                break
            elif pair == "(*":
                start = i
                eligible = bool("".join(masked).strip())
                depth = 1
                i += 2
                continue
            else:
                masked[i] = char
            i += 1
        if quote:
            errors.append(f"L{number} 字符串未闭合，不能可靠划分注释")
        result.append({"mask": "".join(masked), "comments": comments, "source": line,
                       "block_comment_at_start": block_comment_at_start})
    if depth:
        errors.append("块注释未闭合，不能可靠划分注释")
    return result, errors


def logical_units(mask: str) -> list[tuple[int, int]]:
    units, start = [], 0
    for boundary in BOUNDARY.finditer(mask):
        end = boundary.end()
        if mask[start:end].strip():
            units.append((start, end))
        start = end
    if mask[start:].strip():
        units.append((start, len(mask)))
    return [(start + len(mask[start:end]) - len(mask[start:end].lstrip()),
             end - len(mask[start:end]) + len(mask[start:end].rstrip())) for start, end in units]


def compact(text: str) -> str:
    return re.sub(r"[\s`，。；：、,.!！:;]+", "", text).casefold()


def comment_payload(comment: str) -> str:
    """Check the appended note independently, retaining legacy prefix support."""
    payload = comment.rsplit("// 教学补充：", 1)[-1].rsplit(" // ", 1)[-1].strip()
    return re.sub(r'^AI\s*[:：]\s*', '', payload).strip()


def single_action_if(mask: str, units: list[tuple[int, int]]) -> bool:
    """One complete non-nested IF may share a condition-and-action note."""
    if len(units) != 3:
        return False
    parts = [mask[start:end] for start, end in units]
    keywords = re.findall(r"\b(?:IF|THEN|ELSIF|ELSE|END_IF|FOR|DO|END_FOR|CASE|OF|END_CASE|WHILE|END_WHILE|REPEAT|UNTIL|END_REPEAT)\b", mask, re.I)
    return (
        [keyword.upper() for keyword in keywords] == ["IF", "THEN", "END_IF"]
        and re.fullmatch(r"IF\b\s*\S.*\bTHEN", parts[0], re.I) is not None
        and re.fullmatch(r"END_IF\s*;", parts[2], re.I) is not None
        and parts[1].count(":=") == 1
        and re.fullmatch(r"[A-Za-z_]\w*(?:\[[^;\[\]]+\]|\.[A-Za-z_]\w*)*\s*:=\s*[^;]+;", parts[1]) is not None
    )


def low_value(comment: str, source: str) -> str | None:
    comment = comment_payload(comment)
    normalized = compact(comment)
    if not normalized:
        return "缺少有效行内注释"
    if normalized in {compact(item) for item in SYNTAX_ONLY} or normalized.startswith(SYNTAX_PREFIXES):
        return "行内注释只是语法复述或通用填充"
    substantive = re.sub(r"(?:[，。；,;]\s*(?:此处)?(?:作用)?未知\s*)+$", "", comment.strip())
    if FIELD_TRANSLATION.fullmatch(substantive):
        return "注释信息价值低：字段/值直译"
    # This only proves identifier/literal echo, never infers a business purpose.
    tokens = re.findall(r"[A-Za-z_][A-Za-z_0-9]*|\d+(?:\.\d+)?", source)
    remainder = normalized
    for token in sorted(set(tokens), key=len, reverse=True):
        remainder = remainder.replace(token.casefold(), "")
    if remainder in ("", "未知", "此处作用未知", "作用未知"):
        return "注释信息价值低：字段原样或未知填充"
    return None


def numbered_notes(comment: str, count: int) -> list[str] | None:
    comment = comment_payload(comment)
    pieces = comment.split("|")
    notes = []
    for index, piece in enumerate(pieces, 1):
        match = re.fullmatch(r"\s*单元(\d+)\s*[：:]\s*(.*?)\s*", piece)
        if not match or int(match.group(1)) != index:
            return None
        notes.append(match.group(2))
    return notes if len(notes) == count else None


def check_text(raw: str) -> dict:
    all_blocks = fences(raw)
    errors, checked, seen = fence_errors(raw, all_blocks), [], {}
    for block in all_blocks:
        if block["lang"] not in PLC_LANGS:
            continue
        block = dict(block, required_lines=[], required_units=[], closure_lines=[],
                     units=0, covered=0, sha256=digest(block["text"]))
        checked.append(block)
        if not block["closed"]:
            errors.append(f"L{block['line']} PLC 围栏未闭合")
        lines, lexical_errors = lex_lines(block["text"])
        for error in lexical_errors:
            errors.append(f"围栏 L{block['line']}: {error}")
        for offset, line in enumerate(lines, 1):
            number = block["line"] + offset
            units = logical_units(line["mask"])
            required_units = [unit for unit in units if not CLOSE.fullmatch(line["mask"][unit[0]:unit[1]])]
            if units and not required_units and not line["comments"]:
                block["closure_lines"].append(number)
            if required_units:
                block["required_lines"].append(number)
            block["units"] += len(required_units)
            trailing = [value for pos, value in line["comments"] if pos >= (units[-1][1] if units else 0)]
            numbered = numbered_notes(trailing[-1], len(required_units)) if len(required_units) > 1 and trailing else None
            shared = (trailing[-1] if numbered is None and trailing and len(line["comments"]) == 1
                      and single_action_if(line["mask"], units) else None)
            for index, (start, end) in enumerate(units):
                if (start, end) not in required_units:
                    continue
                unit_number = required_units.index((start, end)) + 1
                label = f"L{number} 单元 {unit_number}/{len(required_units)}"
                unit_report = {"line": number, "unit": unit_number, "of": len(required_units),
                               "source": line["source"][start:end], "covered": False}
                block["required_units"].append(unit_report)
                # Multiple actions still need distinct notes. A complete,
                # single-action IF can use one concise condition/action note.
                next_start = units[index + 1][0] if index + 1 < len(units) else len(line["mask"]) + 1
                candidates = [(pos, comment) for pos, comment in line["comments"]
                              if pos >= end and pos < next_start]
                if numbered is not None:
                    candidates = [(end, numbered[required_units.index((start, end))])]
                elif shared is not None:
                    candidates = [(end, shared)]
                if not candidates:
                    errors.append(f"{label} 缺少有效行内注释：{line['source'].strip()}")
                    continue
                comment = "；".join(value for _, value in candidates)
                problem = low_value(comment, line["source"][:candidates[-1][0]])
                if problem:
                    errors.append(f"{label} {problem}：{comment.strip()}")
                    continue
                block["covered"] += 1
                unit_report["covered"] = True
                key = compact(comment_payload(comment))
                source_key = line["mask"][start:end].strip()
                if shared is not None and key in seen and seen[key][0] == number:
                    continue
                if key in seen and seen[key][1] != source_key:
                    errors.append(f"{label} 注释重复粘贴（首次 L{seen[key][0]}），须逐处核对作用：{comment.strip()}")
                else:
                    seen[key] = (number, source_key, block["line"])
    return {"blocks": checked, "errors": errors}


def check_condition_ai(raw: str) -> list[str]:
    """Check IF/ELSIF/ELSE and multiline condition lines in ST/SCL fences.

    Explicit mode for newly annotated output; legacy author comments remain
    accepted by check_text. This checks presence and known empty prose only.
    """
    errors = []
    for block in fences(raw):
        if block['lang'] not in ST_LANGS:
            continue
        lines, lexical_errors = lex_lines(block['text'])
        errors.extend(f"围栏 L{block['line']}: {e}" for e in lexical_errors)
        in_condition = False
        for offset, line in enumerate(lines, 1):
            mask = line['mask']
            condition = bool(re.search(r'\b(?:IF|ELSIF|ELSE)\b', mask, re.I))
            required = bool(mask.strip()) and (condition or in_condition)
            for token in re.findall(r'\b(?:IF|ELSIF|THEN|END_IF)\b', mask, re.I):
                in_condition = token.upper() in {'IF', 'ELSIF'}
            if not required:
                continue
            code_end = len(mask.rstrip())
            notes = [note for pos, note in line['comments'] if pos >= code_end
                     and line['source'][pos:pos+2] == '//'
                     and re.search(r'(?:^\s*|//\s*)AI: ', note)]
            label = f"L{block['line'] + offset} 条件判断行"
            if not notes:
                errors.append(label + ' 缺少 // AI: 逐行条件注释')
            else:
                problem = low_value(notes[-1], line['source'][:code_end])
                if problem:
                    errors.append(label + ' ' + problem)
    return errors


def check_every_code_line(raw: str) -> list[str]:
    """Require a meaningful trailing note on every PLC code/closure line.

    Presence is separate from the existing per-unit quality gate. In particular,
    a block comment followed by more code cannot cover the rest of that line.
    Blank lines and entire block/line comments require no additional note.
    """
    errors = []
    for block in fences(raw):
        if block["lang"] not in PLC_LANGS:
            continue
        lines, lexical_errors = lex_lines(block["text"])
        for error in lexical_errors:
            errors.append(f"围栏 L{block['line']}: {error}")
        for offset, line in enumerate(lines, 1):
            if not line["mask"].strip():
                continue
            code_end = len(line["mask"].rstrip())
            trailing = [(pos, note) for pos, note in line["comments"] if pos >= code_end]
            if not trailing or not any(comment_payload(note) for _, note in trailing):
                errors.append(f"L{block['line'] + offset} 代码行缺少行内注释：{line['source'].strip()}")
            else:
                # check_text already checks executable units. Closures are
                # exempt there, so enforce their note quality only in this mode.
                if CLOSE.fullmatch(line["mask"].strip()):
                    problem = low_value("；".join(note for _, note in trailing), line["source"][:trailing[-1][0]])
                    if problem:
                        errors.append(f"L{block['line'] + offset} {problem}：{line['source'].strip()}")
    return errors


def coverage_summary(block: dict) -> str:
    return (f"  围栏 L{block['line']} {block['lang']}: 覆盖 {block['covered']}/{block['units']}；"
            f"需审查行 {block['required_lines']}；省略的纯结构闭合行 {block['closure_lines']}")


def check_review(raw: str, blocks: list[dict], path: Path | None, required: bool, document_sha256: str | None = None) -> list[str]:
    if not blocks:
        return []
    if path is None:
        return ["语义审查待完成：最终稿须提供 --comment-review 逐块审查记录"] if required else []
    errors = []
    try:
        review = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(review, dict) or review.get("document_sha256") != (document_sha256 or digest(raw)):
            return ["语义审查文档摘要不符或格式错误，请重新审查当前稿"]
        if not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip():
            errors.append("语义审查缺少作者/审查者")
        entries = review.get("blocks")
        if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
            return errors + ["语义审查 blocks 必须是记录列表"]
        if Counter(str(entry.get("fence_line")) for entry in entries) != Counter(str(b["line"]) for b in blocks):
            errors.append("语义审查未逐块覆盖当前全部 PLC 围栏，或含重复/多余记录")
        for block in blocks:
            entry = next((entry for entry in entries if entry.get("fence_line") == block["line"]), {})
            if "omitted_lines" in entry:
                omitted = entry["omitted_lines"]
                seen_lines = set()
                valid = isinstance(omitted, list)
                if valid:
                    for item in omitted:
                        if (not isinstance(item, dict) or type(item.get("line")) is not int
                                or item["line"] not in block["closure_lines"]
                                or item["line"] in seen_lines
                                or not isinstance(item.get("reason"), str) or not item["reason"].strip()):
                            valid = False
                            break
                        seen_lines.add(item["line"])
                if not valid:
                    errors.append(f"语义审查 L{block['line']} omitted_lines 无效：仅可登记当前块未注释的纯结构闭合行，行号须真实且不重复，理由非空")
            if (entry.get("status") != "reviewed" or entry.get("issues") != []
                    or entry.get("code_sha256") != block["sha256"]
                    or entry.get("covered_lines") != block["required_lines"]
                    or any(not isinstance(entry.get(key), str) or not entry[key].strip() for key in ("evidence", "rationale"))):
                errors.append(f"语义审查 L{block['line']} 未通过：需当前摘要、全部行、依据、审查理由和零未解决问题")
    except (OSError, ValueError, TypeError) as exc:
        errors.append(f"语义审查记录不可读：{exc}")
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("documents", type=Path, nargs="+")
    ap.add_argument("--comment-review", type=Path, help="作者逐块语义审查 JSON；只用于单份文档")
    ap.add_argument("--final", action="store_true", help="要求全部块语义审查完成且没有未解决问题")
    ap.add_argument("--require-every-line", action="store_true", help="要求 PLC 围栏内每条非空代码行（包括纯闭合行）有行内注释")
    ap.add_argument("--require-condition-ai", action="store_true", help="要求 ST/SCL 的 IF/ELSIF/ELSE 及跨行条件逐行有 // AI: 尾注")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.comment_review and len(args.documents) != 1:
        ap.error("--comment-review 只接受一份文档")
    reports = []
    for path in args.documents:
        try:
            data = path.read_bytes()
            raw = data.decode("utf-8-sig")
        except (OSError, UnicodeError) as exc:
            reports.append({"path": str(path), "blocks": [], "errors": [str(exc)]})
            continue
        report = check_text(raw)
        if args.require_condition_ai:
            report["errors"] += check_condition_ai(raw)
        if args.require_every_line:
            report["errors"] += check_every_code_line(raw)
        report["errors"] += check_review(raw, report["blocks"], args.comment_review, args.final, hashlib.sha256(data).hexdigest())
        report.update(path=str(path), semantic_review="recorded" if report["blocks"] and args.comment_review and not report["errors"] else "pending")
        reports.append(report)
    if args.json:
        print(json.dumps(reports, ensure_ascii=False, indent=2))
    else:
        for report in reports:
            print(f"{report['path']}: PLC 块 {len(report['blocks'])}；确定性错误 {len(report['errors'])}")
            for block in report["blocks"]:
                print(coverage_summary(block))
            for error in report["errors"]:
                print(f"ERROR {error}")
            print("语义审查：" + ("作者记录已核验（非机器语义证明）" if report.get("semantic_review") == "recorded" else "待逐块审查；确定性通过不代表注释质量全部合格"))
    return int(any(report["errors"] for report in reports))


if __name__ == "__main__":
    raise SystemExit(main())
