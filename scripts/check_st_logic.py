#!/usr/bin/env python3
"""ST 静态逻辑检查：块配对、CASE 分支、状态表、常量安全、死代码与声明卫生。

用法：
    python3 -B scripts/check_st_logic.py <文件或目录>... [--json]
                                  [--min-severity error|warn|info] [--quiet]

只做文本级规则检查，不编译、不运行 ST。注释 (* ... *)（可嵌套）、// 行注释与
单引号字符串先被替换成空格（保留换行），所以所有行号都指向原始源文件真实行。
目录递归只收集 *.st，按路径排序，输出顺序确定。
"""

from __future__ import annotations

import argparse
import bisect
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

SEVERITY_LABEL = {"error": "ERROR", "warn": "WARN", "info": "INFO"}
SEVERITY_RANK = {"error": 0, "warn": 1, "info": 2}
SEVERITIES = ("error", "warn", "info")

# 块类型：开始关键字 -> 家族；结束关键字 -> 家族。
OPEN_BLOCK = {
    "IF": "IF",
    "CASE": "CASE",
    "FOR": "FOR",
    "WHILE": "WHILE",
    "REPEAT": "REPEAT",
    "VAR": "VAR",
    "VAR_INPUT": "VAR",
    "VAR_OUTPUT": "VAR",
    "VAR_IN_OUT": "VAR",
    "VAR_TEMP": "VAR",
    "VAR_STAT": "VAR",
    "VAR_EXTERNAL": "VAR",
    "VAR_GLOBAL": "VAR",
    "VAR_CONFIG": "VAR",
    "VAR_ACCESS": "VAR",
    "FUNCTION_BLOCK": "FUNCTION_BLOCK",
    "FUNCTION": "FUNCTION",
    "TYPE": "TYPE",
    "STRUCT": "STRUCT",
}

CLOSE_BLOCK = {
    "END_IF": "IF",
    "END_CASE": "CASE",
    "END_FOR": "FOR",
    "END_WHILE": "WHILE",
    "END_REPEAT": "REPEAT",
    "END_VAR": "VAR",
    "END_FUNCTION_BLOCK": "FUNCTION_BLOCK",
    "END_FUNCTION": "FUNCTION",
    "END_TYPE": "TYPE",
    "END_STRUCT": "STRUCT",
}

BLOCK_KEYWORDS = {**{kind: (kind, "END_" + kind) for kind in OPEN_BLOCK.values()}}
BLOCK_KEYWORDS["VAR"] = ("VAR/VAR_INPUT/...", "END_VAR")
BLOCK_ORDER = ("IF", "CASE", "FOR", "WHILE", "REPEAT", "VAR",
               "FUNCTION_BLOCK", "FUNCTION", "TYPE", "STRUCT")
CONTROL_KINDS = {"IF", "CASE", "FOR", "WHILE", "REPEAT"}
VAR_OPENERS = {"VAR", "VAR_INPUT", "VAR_OUTPUT", "VAR_IN_OUT", "VAR_TEMP",
               "VAR_STAT", "VAR_EXTERNAL", "VAR_GLOBAL", "VAR_CONFIG", "VAR_ACCESS"}

# 需要参与扫描的其它关键字。
EXTRA_WORDS = {"ELSE", "ELSIF", "RETURN", "EXIT", "MOD", "TRUE", "FALSE"}

WORD = re.compile(r"[A-Za-z_]\w*")


@dataclass(frozen=True)
class Token:
    word: str
    line: int
    start: int
    end: int


@dataclass(frozen=True)
class Finding:
    line: int
    severity: str
    code: str
    message: str


def mask_source(text: str) -> str:
    """屏蔽注释与字符串，保留换行和字符位置。"""
    out = list(text)
    size = len(text)

    def blank(first: int, last: int) -> None:
        for index in range(first, min(last, size)):
            if out[index] not in "\r\n":
                out[index] = " "

    index = 0
    depth = 0
    while index < size:
        if depth:
            if text.startswith("(*", index):
                depth += 1
                blank(index, index + 2)
                index += 2
            elif text.startswith("*)", index):
                depth -= 1
                blank(index, index + 2)
                index += 2
            else:
                blank(index, index + 1)
                index += 1
            continue
        if text.startswith("(*", index):
            depth = 1
            blank(index, index + 2)
            index += 2
        elif text.startswith("//", index):
            stop = text.find("\n", index)
            if stop < 0:
                stop = size
            blank(index, stop)
            index = stop
        elif text[index] == "'":
            blank(index, index + 1)
            index += 1
            while index < size:
                if text.startswith("$", index) and index + 1 < size:
                    blank(index, index + 2)
                    index += 2
                    continue
                if text[index] == "'":
                    if text.startswith("''", index):
                        blank(index, index + 2)
                        index += 2
                        continue
                    blank(index, index + 1)
                    index += 1
                    break
                blank(index, index + 1)
                index += 1
        else:
            index += 1
    return "".join(out)


def line_starts(text: str) -> list[int]:
    starts = [0]
    for match in re.finditer(r"\n", text):
        starts.append(match.end())
    return starts


def tokenize(masked: str, starts: list[int]) -> list[Token]:
    tokens: list[Token] = []
    for match in WORD.finditer(masked):
        word = match.group(0).upper()
        if word in OPEN_BLOCK or word in CLOSE_BLOCK or word in EXTRA_WORDS:
            line = bisect.bisect_right(starts, match.start())
            tokens.append(Token(word, line, match.start(), match.end()))
    return tokens


def depth_events(tokens: list[Token]) -> tuple[list[int], list[int]]:
    """控制结构（IF/CASE/FOR/WHILE/REPEAT）嵌套深度事件。"""
    positions: list[int] = []
    depths: list[int] = []
    depth = 0
    for token in tokens:
        if token.word in OPEN_BLOCK and OPEN_BLOCK[token.word] in CONTROL_KINDS:
            depth += 1
        elif token.word in CLOSE_BLOCK and CLOSE_BLOCK[token.word] in CONTROL_KINDS:
            depth -= 1
        else:
            continue
        positions.append(token.start)
        depths.append(depth)
    return positions, depths


def depth_at(events: tuple[list[int], list[int]], position: int) -> int:
    positions, depths = events
    index = bisect.bisect_left(positions, position)
    return depths[index - 1] if index else 0


# ---------------------------------------------------------------- STB001


def check_block_balance(tokens: list[Token]) -> list[Finding]:
    findings: list[Finding] = []
    opens: dict[str, list[int]] = {}
    closes: dict[str, list[int]] = {}
    for token in tokens:
        if token.word in OPEN_BLOCK:
            opens.setdefault(OPEN_BLOCK[token.word], []).append(token.line)
        elif token.word in CLOSE_BLOCK:
            closes.setdefault(CLOSE_BLOCK[token.word], []).append(token.line)
    for kind in BLOCK_ORDER:
        opened = opens.get(kind, [])
        closed = closes.get(kind, [])
        begin, finish = BLOCK_KEYWORDS[kind]
        if len(opened) > len(closed):
            extra_line = opened[len(closed)]
            findings.append(Finding(
                extra_line, "error", "STB001",
                f"{begin} 块缺少配对的 {finish}（已开 {len(opened)} 个，已闭 {len(closed)} 个）"))
        elif len(closed) > len(opened):
            extra_line = closed[len(opened)]
            findings.append(Finding(
                extra_line, "error", "STB001",
                f"多出的 {finish}：没有对应的 {begin}（已开 {len(opened)} 个，已闭 {len(closed)} 个）"))
    return findings


# ------------------------------------------------------- STB002/003/004

_LABEL_ITEM = r"-?\d+(?:[ \t]*\.\.[ \t]*-?\d+)?"
_CASE_LABELS = re.compile(
    r"(?im)(?:^|;|\bOF\b)[ \t]*(" + _LABEL_ITEM + r"(?:[ \t]*,[ \t]*" + _LABEL_ITEM + r")*)[ \t]*:(?!=)")

_RANGE = re.compile(r"^([-+]?\d+)[ \t]*\.\.[ \t]*([-+]?\d+)$")


def case_pairs(tokens: list[Token]) -> list[tuple[Token, Token]]:
    stack: list[Token] = []
    pairs: list[tuple[Token, Token]] = []
    for token in tokens:
        if token.word == "CASE":
            stack.append(token)
        elif token.word == "END_CASE" and stack:
            pairs.append((stack.pop(), token))
    pairs.sort(key=lambda pair: pair[0].start)
    return pairs


def check_cases(masked: str, tokens: list[Token],
                events: tuple[list[int], list[int]]) -> list[Finding]:
    findings: list[Finding] = []
    pairs = case_pairs(tokens)
    label_matches = list(_CASE_LABELS.finditer(masked))
    for opener, closer in pairs:
        body_start, body_end = opener.end, closer.start
        base = depth_at(events, body_start)
        if not masked[body_start:body_end].strip():
            continue
        has_else = False
        for token in tokens:
            if token.start < body_start or token.start >= body_end:
                continue
            if token.word == "ELSE" and depth_at(events, token.start) == base:
                has_else = True
                break
        if not has_else:
            findings.append(Finding(
                opener.line, "warn", "STB002",
                "CASE 缺少 ELSE 分支：未覆盖的取值会被静默跳过，状态机容易停在中间态"))

        seen: dict[int, int] = {}
        for match in label_matches:
            if match.start() < body_start or match.end() > body_end:
                continue
            colon = match.end() - 1
            if depth_at(events, colon) != base:
                continue
            line = bisect.bisect_right(line_starts(masked), match.start(1))
            for item in match.group(1).split(","):
                text = item.strip()
                if not text:
                    continue
                bounds = _RANGE.match(text)
                if bounds:
                    low, high = int(bounds.group(1)), int(bounds.group(2))
                    if high < low:
                        findings.append(Finding(
                            line, "error", "STB004",
                            f"CASE 区间 {low}..{high} 上下界颠倒，该分支永远不会命中"))
                        continue
                    values = range(low, high + 1) if high - low <= 1000 else (low, high)
                else:
                    try:
                        values = (int(text),)
                    except ValueError:
                        continue
                for value in values:
                    if value in seen:
                        findings.append(Finding(
                            line, "error", "STB003",
                            f"CASE 标签值 {value} 重复（首次出现在第 {seen[value]} 行）"))
                        break
                    seen[value] = line
    return findings


# ------------------------------------------------------- STB005/006/007/008/009

_ROW_ASSIGN = re.compile(
    r"\b([A-Za-z_]\w*)\s*\[\s*(-?\d+)\s*\]\s*\.\s*"
    r"(nState|nParent|xLeaf|nEntryAct|nTimeoutMS|nFrom|nEvent|wGuard|wBlock|nTo|nAction|nTimeMS|nPriority)"
    r"\s*:=\s*([^;]*);", re.IGNORECASE)
_INIT_STATE = re.compile(r"\bnInitState\s*:=\s*(-?\d+)", re.IGNORECASE)
_ARRAY_DECL = re.compile(r"\b([A-Za-z_]\w*)\s*:\s*ARRAY\s*\[", re.IGNORECASE)
_INT_CONST = re.compile(
    r"\b([A-Za-z_]\w*)\s*:\s*(?:INT|DINT|SINT|UINT|UDINT|USINT)\s*:=\s*(-?\d+)\s*;", re.IGNORECASE)

NODE_FIELDS = {"nstate", "nparent", "xleaf", "nentryact", "ntimeoutms"}
TRANS_FIELDS = {"nfrom", "nto", "nevent", "wguard", "wblock", "naction", "ntimems", "npriority"}


def parse_literal(text: str) -> int | None:
    """解析 ST 整数字面量；TRUE/FALSE 按 1/0。"""
    text = text.strip()
    if re.fullmatch(r"[+-]?\d+", text):
        return int(text)
    match = re.fullmatch(r"(\d+)#([0-9A-Fa-f_]+)", text)
    if match:
        try:
            return int(match.group(2).replace("_", ""), int(match.group(1)))
        except ValueError:
            return None
    upper = text.upper()
    if upper == "TRUE":
        return 1
    if upper == "FALSE":
        return 0
    return None


def node_table_for(trans_name: str) -> str:
    return trans_name.replace("Trans", "Nodes")


def collect_tables(masked: str):
    """按变量前缀收集逐行赋值：{前缀: {行号: {字段: (值, 行)}}}。"""
    tables: dict[str, dict[int, dict[str, tuple[int | None, int, str]]]] = {}
    starts = line_starts(masked)
    for match in _ROW_ASSIGN.finditer(masked):
        name, row = match.group(1), int(match.group(2))
        field = match.group(3).lower()
        raw = match.group(4).strip()
        value = parse_literal(raw)
        line = bisect.bisect_right(starts, match.start())
        tables.setdefault(name, {}).setdefault(row, {})[field] = (value, line, raw)
    return tables


def array_bounds(masked: str) -> dict[str, tuple[int, int]]:
    constants = {match.group(1).upper(): int(match.group(2))
                 for match in _INT_CONST.finditer(masked)}
    # 键统一 casefold，调用侧按同一规则查找。
    bounds: dict[str, tuple[int, int]] = {}
    for match in _ARRAY_DECL.finditer(masked):
        close = masked.find("]", match.end())
        if close < 0:
            continue
        first = masked[match.end():close].split(",")[0]
        parts = re.match(r"\s*(-?\d+|[A-Za-z_]\w*)\s*\.\.\s*(-?\d+|[A-Za-z_]\w*)", first)
        if not parts:
            continue

        def value(token: str) -> int | None:
            if re.fullmatch(r"-?\d+", token):
                return int(token)
            return constants.get(token.upper())

        low, high = value(parts.group(1)), value(parts.group(2))
        if low is None or high is None:
            continue
        bounds[match.group(1).casefold()] = (low, high)
    return bounds


def classify_tables(tables):
    """返回 (节点表集合, 转移表集合)。"""
    nodes = {name for name, rows in tables.items()
             if any(set(fields) & NODE_FIELDS for fields in rows.values())}
    trans = {name for name, rows in tables.items()
             if any(set(fields) & TRANS_FIELDS for fields in rows.values())}
    return nodes, trans


def node_states(rows) -> dict[int, int]:
    """状态号 -> 行号；没有 nState 赋值时退回数组下标。"""
    states: dict[int, int] = {}
    for row, fields in rows.items():
        if "nstate" in fields:
            state = fields["nstate"][0]
            if state is not None:
                states[state] = fields["nstate"][1]
        else:
            states[row] = fields[next(iter(fields))][1] if fields else 0
    return states


def check_state_tables(masked: str) -> list[Finding]:
    findings: list[Finding] = []
    tables = collect_tables(masked)
    nodes, trans = classify_tables(tables)
    inits = [(int(match.group(1)), bisect.bisect_right(line_starts(masked), match.start()))
             for match in _INIT_STATE.finditer(masked)]
    init_state = inits[0][0] if inits else None

    # 节点表各自关联的转移表（前缀把 Trans 换成 Nodes）；找不到就退回全文件的 nTo。
    targets_by_node: dict[str, set[int]] = {}
    for name in trans:
        fields_all = tables[name].values()
        targets = {fields["nto"][0] for fields in fields_all
                   if "nto" in fields and fields["nto"][0] is not None}
        node_name = node_table_for(name)
        if node_name in nodes:
            targets_by_node.setdefault(node_name, set()).update(targets)

    for name in sorted(trans):
        rows = tables[name]
        node_name = node_table_for(name)
        if node_name not in nodes:
            continue
        states = node_states(tables[node_name])
        if not states:
            continue
        allowed = set(states)

        # STB005：nFrom（-1 表示全局转移）与 nTo 必须是节点表中的状态。
        for row in sorted(rows):
            for field in ("nfrom", "nto"):
                if field not in rows[row]:
                    continue
                value, line, _ = rows[row][field]
                if value is None:
                    continue
                if field == "nfrom" and value == -1:
                    continue
                if value not in allowed:
                    label = "nFrom" if field == "nfrom" else "nTo"
                    sample = ", ".join(map(str, sorted(allowed)[:16]))
                    if len(allowed) > 16:
                        sample += ", ..."
                    findings.append(Finding(
                        line, "error", "STB005",
                        f"状态表 {name}[{row}].{label} = {value} "
                        f"不在节点表 {node_name} 的状态集合 {len(allowed)} 个状态内"
                        f"（已知：{sample}）"))

        # STB006：同一转移表内 (nFrom, nEvent, wGuard, wBlock) 完全重复。
        seen_edges: dict[tuple, tuple[int, int]] = {}
        for row in sorted(rows):
            fields = rows[row]
            if not {"nfrom", "nevent", "nto"} <= set(fields):
                continue

            def raw(key: str) -> str:
                return " ".join(fields.get(key, (None, 0, ""))[2].split()).upper()

            edge = (fields["nfrom"][0], fields["nevent"][0], raw("wguard"), raw("wblock"))
            if edge in seen_edges:
                first_row, first_line = seen_edges[edge]
                findings.append(Finding(
                    fields["nfrom"][1], "error", "STB006",
                    f"状态表 {name} 重复转移：与第 {first_line} 行（行 {first_row}）"
                    f"的 nFrom={edge[0]}、nEvent={edge[1]}、wGuard={raw('wguard') or '0'}、"
                    f"wBlock={raw('wblock') or '0'} 完全相同"))
            else:
                seen_edges[edge] = (row, fields["nfrom"][1])

        # STB009：nTimeMS / nTimeoutMS 为负。
        for row in sorted(rows):
            for field in ("ntimems", "ntimeoutms"):
                if field not in rows[row]:
                    continue
                value, line, _ = rows[row][field]
                if value is not None and value < 0:
                    findings.append(Finding(
                        line, "error", "STB009",
                        f"状态表 {name}[{row}].{field} = {value} 为负，时间必须非负"))

    # 节点表：STB007 不可达叶子、STB008 复合状态无子状态/父链成环、STB009 负超时。
    for node_name in sorted(nodes):
        rows = tables[node_name]
        states = node_states(rows)
        if not states:
            continue
        parents = {fields["nparent"][0] for fields in rows.values()
                   if "nparent" in fields and fields["nparent"][0] is not None}
        roots = sorted(
            (fields["nstate"][0] if "nstate" in fields else row)
            for row, fields in rows.items()
            if "nparent" in fields and fields["nparent"][0] == -1)
        default_initial = roots[0] if roots else None
        # 优先用同名前缀转移表的 nTo；没有配对转移表时退回全文件 nTo。
        all_targets = targets_by_node.get(node_name)
        if all_targets is None:
            all_targets = {fields["nto"][0] for name in trans
                           for fields in tables[name].values()
                           if "nto" in fields and fields["nto"][0] is not None}

        for row in sorted(rows):
            fields = rows[row]
            state = fields["nstate"][0] if "nstate" in fields else row
            if state is None:
                continue
            if "xleaf" in fields and fields["xleaf"][0] == 1:
                is_initial = (init_state is not None and init_state == state) or \
                    (state == default_initial)
                if not is_initial and state not in all_targets:
                    findings.append(Finding(
                        fields["xleaf"][1], "warn", "STB007",
                        f"不可达叶子状态 {state}（{node_name}[{row}]）：既不是初始态，"
                        "也从未出现在任何转移的 nTo"))
            if "xleaf" in fields and fields["xleaf"][0] == 0 and state not in parents:
                findings.append(Finding(
                    fields["xleaf"][1], "warn", "STB008",
                    f"复合状态 {state}（{node_name}[{row}]）声明 xLeaf := FALSE，"
                    "但没有任何其它节点的 nParent 指向它"))
            if "ntimeoutms" in fields:
                value, line, _ = fields["ntimeoutms"]
                if value is not None and value < 0:
                    findings.append(Finding(
                        line, "error", "STB009",
                        f"节点表 {node_name}[{row}].nTimeoutMS = {value} 为负，时间必须非负"))

        # nParent 自指或父链成环（超过 8 步仍未到 -1）。
        parent_of: dict[int, tuple[int, int]] = {}
        for row in sorted(rows):
            fields = rows[row]
            state = fields["nstate"][0] if "nstate" in fields else row
            if state is None or "nparent" not in fields:
                continue
            parent, line, _ = fields["nparent"]
            if parent is not None:
                parent_of[state] = (parent, line)
        for state in sorted(parent_of):
            parent, line = parent_of[state]
            if parent == state:
                findings.append(Finding(
                    line, "error", "STB008",
                    f"节点表 {node_name} 的状态 {state}.nParent 指向自身"))
                continue
            path = [state]
            cursor = parent
            for _ in range(8):
                if cursor == -1 or cursor not in parent_of:
                    break
                if cursor in path:
                    findings.append(Finding(
                        line, "error", "STB008",
                        f"节点表 {node_name} 的 nParent 链成环："
                        f"{' -> '.join(map(str, path + [cursor]))}"))
                    break
                path.append(cursor)
                cursor = parent_of[cursor][0]
            else:
                findings.append(Finding(
                    line, "error", "STB008",
                    f"节点表 {node_name} 的 nParent 链超过 8 步仍未到 -1，疑似成环"))
    return findings


# ------------------------------------------------------- STB010/011/012/016

_INDEX_USE = re.compile(r"\b([A-Za-z_]\w*)\s*\[\s*(-?\d+)\s*\]")
_DIV_ZERO = re.compile(r"(?<![\w.])/\s*0(?:\.0+)?(?![\w.])|(?<![\w.])MOD\s+0(?:\.0+)?(?![\w.])",
                       re.IGNORECASE)
_TAUTOLOGY = (
    (re.compile(r"\bIF\s+TRUE\b", re.IGNORECASE), "IF TRUE"),
    (re.compile(r"\bIF\s+FALSE\b", re.IGNORECASE), "IF FALSE"),
    (re.compile(r"\bELSIF\s+TRUE\b", re.IGNORECASE), "ELSIF TRUE"),
    (re.compile(r"\bAND\s+FALSE\b", re.IGNORECASE), "AND FALSE"),
    (re.compile(r"\bOR\s+TRUE\b", re.IGNORECASE), "OR TRUE"),
)
_PT_ZERO = re.compile(r"\bPT\s*:=\s*T#\s*(\d+(?:\.\d+)?)\s*(MS|S)\b(?![0-9.])", re.IGNORECASE)
_IN_FALSE = re.compile(r"\bIN\s*:=\s*FALSE\b", re.IGNORECASE)


def enclosing_call(masked: str, position: int) -> tuple[int, int] | None:
    """返回包住 position 的最近一层括号区间（开括号下标, 闭括号下标）。"""
    depth = 0
    index = position
    while index >= 0:
        char = masked[index]
        if char == ")":
            depth += 1
        elif char == "(":
            if depth == 0:
                break
            depth -= 1
        index -= 1
    if index < 0:
        return None
    close = masked.find(")", position)
    return (index, close if close >= 0 else len(masked))


def check_constants(masked: str) -> list[Finding]:
    findings: list[Finding] = []
    starts = line_starts(masked)

    bounds = array_bounds(masked)
    for match in _INDEX_USE.finditer(masked):
        name = match.group(1)
        # ST 标识符大小写不敏感：声明与使用的大小写差异不得导致漏检。
        key = name.casefold()
        if name.upper() in {"ARRAY", "STRING", "WSTRING"} or key not in bounds:
            continue
        value = int(match.group(2))
        low, high = bounds[key]
        if value < low or value > high:
            line = bisect.bisect_right(starts, match.start())
            findings.append(Finding(
                line, "error", "STB010",
                f"常量下标越界：{name}[{value}] 超出声明范围 {low}..{high}"))

    for match in _DIV_ZERO.finditer(masked):
        line = bisect.bisect_right(starts, match.start())
        findings.append(Finding(
            line, "error", "STB011",
            f"常量除零/模零：“{match.group(0).strip()}” 在运行时会产生未定义结果"))

    for pattern, text in _TAUTOLOGY:
        for match in pattern.finditer(masked):
            line = bisect.bisect_right(starts, match.start())
            findings.append(Finding(
                line, "warn", "STB012",
                f"恒真/恒假条件：{text} 使该分支恒定，条件本身已失去判断意义"))

    for match in _PT_ZERO.finditer(masked):
        try:
            zero = float(match.group(1)) == 0.0
        except ValueError:
            zero = False
        if not zero:
            continue
        # IN := FALSE 时调用只是复位/停表，PT 取零是有意为之，不算问题。
        span = enclosing_call(masked, match.start())
        if span is not None and _IN_FALSE.search(masked[span[0]:span[1]]):
            continue
        line = bisect.bisect_right(starts, match.start())
        findings.append(Finding(
            line, "warn", "STB016",
            f"定时器 PT 常量为零（{match.group(0).strip()}），定时器会立即完成或永不生效"))
    return findings


# ------------------------------------------------------- STB013/014

_DECL = re.compile(r"^\s*((?:[A-Za-z_]\w*\s*,\s*)*[A-Za-z_]\w*)\s*:\s*([A-Za-z_][\w.]*)")


def var_blocks(tokens: list[Token]) -> list[tuple[Token, Token]]:
    stack: list[Token] = []
    blocks: list[tuple[Token, Token]] = []
    for token in tokens:
        if token.word in VAR_OPENERS:
            stack.append(token)
        elif token.word == "END_VAR" and stack:
            blocks.append((stack.pop(), token))
    blocks.sort(key=lambda pair: pair[0].start)
    return blocks


def declarations(masked: str, blocks: list[tuple[Token, Token]]):
    """返回 [(名称, 类型, 行号)]，只取 VAR 区段内的简单声明。"""
    starts = line_starts(masked)
    items: list[tuple[str, str, int]] = []
    for opener, closer in blocks:
        body = masked[opener.end:closer.start]
        for statement in body.split(";"):
            match = _DECL.match(statement)
            if not match:
                continue
            line = bisect.bisect_right(starts, opener.end + statement.find(match.group(1)))
            type_name = match.group(2)
            for name in match.group(1).split(","):
                items.append((name.strip(), type_name, line))
    return items


def check_declarations(masked: str, tokens: list[Token]) -> list[Finding]:
    findings: list[Finding] = []
    blocks = var_blocks(tokens)
    plain = [pair for pair in blocks if pair[0].word == "VAR"]
    plain_items = declarations(masked, plain)
    all_items = declarations(masked, blocks)

    for name, type_name, line in plain_items:
        if type_name.upper() != "BOOL":
            continue
        true_hits, false_hits, other_hits = 0, 0, 0
        for match in re.finditer(rf"\b{re.escape(name)}\s*:=\s*([^;]*);", masked):
            right = match.group(1).strip()
            if re.match(r"TRUE\b", right, re.IGNORECASE):
                true_hits += 1
            elif re.match(r"FALSE\b", right, re.IGNORECASE):
                false_hits += 1
            else:
                other_hits += 1
        if true_hits and not false_hits and not other_hits:
            findings.append(Finding(
                line, "info", "STB013",
                f"BOOL 变量 {name} 只出现 := TRUE，从未显式复位；确认是否有意保持"))

    for name, type_name, line in all_items:
        if not type_name.upper().startswith("FB_"):
            continue
        if re.search(rf"\b{re.escape(name)}\s*\(", masked):
            continue
        findings.append(Finding(
            line, "warn", "STB014",
            f"FB 实例 {name}（{type_name}）已声明但文件中从未调用 {name}(...)"))
    return findings


# ---------------------------------------------------------------- STB015

_LABEL_START = re.compile(r"^-?\d+\s*:(?!=)|^[A-Za-z_]\w*\s*:(?!=)")


def is_block_boundary(text: str) -> bool:
    first = WORD.match(text)
    if first and first.group(0).upper() in CLOSE_BLOCK:
        return True
    upper = text.upper()
    if upper.startswith("ELSE") or upper.startswith("ELSIF"):
        return True
    return bool(_LABEL_START.match(text))


def check_unreachable(masked: str, tokens: list[Token]) -> list[Finding]:
    findings: list[Finding] = []
    starts = line_starts(masked)
    lines = masked.split("\n")
    for token in tokens:
        if token.word not in ("RETURN", "EXIT"):
            continue
        index = token.line - 1
        column = token.end - starts[index]
        line = lines[index]
        semicolon = line.find(";", column)
        rest = line[semicolon + 1:] if semicolon >= 0 else line[column:]
        rest = rest.strip().lstrip(";").strip()
        target: int | None = None
        if rest:
            if not is_block_boundary(rest):
                target = index + 1
        else:
            cursor = index + 1
            while cursor < len(lines):
                body = lines[cursor].strip()
                body = body.lstrip(";").strip()
                if not body:
                    cursor += 1
                    continue
                if is_block_boundary(body):
                    break
                target = cursor + 1
                break
        if target is not None:
            findings.append(Finding(
                target, "info", "STB015",
                f"{token.word} 之后到块结束之间仍有语句，这些语句永远不会执行"))
    return findings


# ---------------------------------------------------------------- 驱动


def check_text(text: str) -> list[Finding]:
    masked = mask_source(text)
    starts = line_starts(masked)
    tokens = tokenize(masked, starts)
    events = depth_events(tokens)
    findings: list[Finding] = []
    findings.extend(check_block_balance(tokens))
    findings.extend(check_cases(masked, tokens, events))
    findings.extend(check_state_tables(masked))
    findings.extend(check_constants(masked))
    findings.extend(check_declarations(masked, tokens))
    findings.extend(check_unreachable(masked, tokens))
    unique: dict[tuple[int, str, str], Finding] = {}
    for finding in findings:
        unique.setdefault((finding.line, finding.code, finding.message), finding)
    return sorted(unique.values(), key=lambda item: (item.line, item.code, item.message))


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


class Parser(argparse.ArgumentParser):
    """参数错误按约定返回 1（argparse 默认是 2）。"""

    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        print(f"ERROR 参数错误：{message}", file=sys.stderr)
        raise SystemExit(1)


def collect_files(raw_paths: list[str]) -> tuple[list[Path], list[str]]:
    files: list[Path] = []
    problems: list[str] = []
    for raw in raw_paths:
        path = Path(raw)
        if path.is_dir():
            found = sorted((item for item in path.rglob("*.st") if item.is_file()),
                           key=lambda item: item.as_posix())
            files.extend(found)
        elif path.is_file():
            files.append(path)
        else:
            problems.append(f"ERROR 找不到文件或目录：{raw}")
    return list(dict.fromkeys(files)), problems


def main(argv: list[str] | None = None) -> int:
    ap = Parser(description="ST 静态逻辑检查：块配对、CASE、状态表、常量安全与死代码")
    ap.add_argument("paths", nargs="+", metavar="文件或目录")
    ap.add_argument("--json", action="store_true", help="输出 JSON（files/findings/summary）")
    ap.add_argument("--min-severity", choices=SEVERITIES, default="info",
                    help="只显示不低于该级别的发现（默认 info）")
    ap.add_argument("--quiet", action="store_true", help="只输出摘要")
    args = ap.parse_args(argv)

    files, problems = collect_files(args.paths)
    for message in problems:
        print(message, file=sys.stderr)
    if problems:
        return 1

    reports: list[tuple[str, list[Finding]]] = []
    failed = False
    for path in files:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"ERROR 无法读取文件：{path}（{exc}）", file=sys.stderr)
            failed = True
            continue
        reports.append((display_path(path), check_text(text)))

    errors = sum(1 for _, items in reports for item in items if item.severity == "error")
    warnings = sum(1 for _, items in reports for item in items if item.severity == "warn")
    infos = sum(1 for _, items in reports for item in items if item.severity == "info")
    summary = {"files": len(reports), "errors": errors,
               "warnings": warnings, "infos": infos}

    if args.json:
        payload = {
            "files": [name for name, _ in reports],
            "findings": [
                {"file": name, "line": item.line,
                 "severity": item.severity, "code": item.code,
                 "message": item.message}
                for name, items in reports for item in items
                if SEVERITY_RANK[item.severity] <= SEVERITY_RANK[args.min_severity]
            ],
            "summary": summary,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if not args.quiet:
            for name, items in reports:
                for item in items:
                    if SEVERITY_RANK[item.severity] > SEVERITY_RANK[args.min_severity]:
                        continue
                    print(f"{name}:{item.line}: {SEVERITY_LABEL[item.severity]} "
                          f"{item.code} {item.message}")
        print(f"共检查 {summary['files']} 个文件：{errors} 错误、{warnings} 警告、{infos} 提示")

    if failed or errors:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
