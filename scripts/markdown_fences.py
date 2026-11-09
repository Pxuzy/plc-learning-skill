#!/usr/bin/env python3
"""Shared fenced-code views: CommonMark delimiters, quotes and space-indented lists.

This is a fenced-block reader, not a complete Markdown renderer. Tabs in container
indentation are diagnosed rather than silently treated as an absent PLC fence.
Original physical line numbers and code trailing spaces are retained.
"""
from __future__ import annotations
import re

OPEN = re.compile(r'^ {0,3}(`{3,}|~{3,})(.*)$')
QUOTE = re.compile(r'^ {0,3}>[ \t]?')
LIST = re.compile(r'^( *)(?:[-+*]|\d{1,9}[.)])( {1,4})(.*)$')
ST_LANGS = {'st', 'pascal', 'scl', 'structured-text', 'structured_text', 'structuredtext', 'iecst'}
PLC_LANGS = ST_LANGS | {'iec', 'iec61131-3', 'plc', 'fb', 'il', 'awl', 'ld', 'lad',
                         'ladder', 'ladder-logic', 'fbd', 'sfc', 'iec61131'}


def fence_language(info: str) -> str:
    tokens = info.strip().split()
    return tokens[0].strip('{}.').lower() if tokens else ''


def unquote(line: str) -> tuple[str, int]:
    depth = 0
    while match := QUOTE.match(line):
        line = line[match.end():]
        depth += 1
    return line, depth


def parse_fences(raw: str) -> list[dict]:
    lines = raw.splitlines()
    blocks = []
    index, list_indent, list_quote = 0, 0, 0
    while index < len(lines):
        candidate, quote_depth = unquote(lines[index])
        if quote_depth != list_quote:
            list_indent = 0
        list_quote = quote_depth
        marker = LIST.match(candidate)
        if marker:
            # The marker's content indentation is removed from continuation lines.
            list_indent = marker.start(3)
            candidate = marker[3]
        elif list_indent:
            spaces = len(candidate) - len(candidate.lstrip(' '))
            if candidate.strip() and spaces < list_indent:
                list_indent = 0
            else:
                candidate = candidate[min(spaces, list_indent):]
        match = OPEN.fullmatch(candidate)
        if not match or (match[1][0] == '`' and '`' in match[2]):
            index += 1
            continue
        delimiter, info = match.groups()
        fence_indent = len(candidate) - len(candidate.lstrip(' '))
        start = index
        index += 1
        closing = re.compile(r'^ {0,3}' + re.escape(delimiter[0]) + '{' + str(len(delimiter)) + r',}[ \t]*$')
        content = []
        closed = False
        while index < len(lines):
            line = lines[index]
            depth = 0
            for _ in range(quote_depth):
                quote = QUOTE.match(line)
                if not quote:
                    break
                line = line[quote.end():]
                depth += 1
            if depth < quote_depth and line.strip():
                break
            spaces = len(line) - len(line.lstrip(' '))
            if list_indent and line.strip() and spaces < list_indent:
                break
            line = line[min(spaces, list_indent):]
            if closing.fullmatch(line):
                closed = True
                break
            # CommonMark removes up to opener indentation, never code tail spaces.
            spaces = len(line) - len(line.lstrip(' '))
            content.append(line[min(spaces, fence_indent):])
            index += 1
        blocks.append({'line': start + 1, 'lang': fence_language(info),
                       'end_line': index + 1 if closed else index,
                       'delimiter': delimiter, 'text': '\n'.join(content),
                       'source_lines': content, 'closed': closed,
                       'quote_depth': quote_depth, 'list_indent': list_indent})
        if closed:
            index += 1
    return blocks


def body_view(raw: str) -> str:
    """Hide fenced content while preserving offsets/newlines; opener marks content.

    Keeping one non-heading character at an opener lets a code-only section count
    as nonempty. No code heading, link, table or status can enter the prose view.
    """
    lines = raw.splitlines(keepends=True)
    for block in parse_fences(raw):
        for index in range(block['line'] - 1, min(block['end_line'], len(lines))):
            lines[index] = ''.join(c if c in '\r\n' else ' ' for c in lines[index])
        start = block['line'] - 1
        if lines[start].strip('\r\n'):
            lines[start] = '·' + lines[start][1:]
    return ''.join(lines)


def fence_diagnostics(raw: str, languages: set[str] = PLC_LANGS) -> list[str]:
    blocks = parse_fences(raw)
    errors = [f"L{b['line']} 围栏未闭合，无法证明后续源码已覆盖" for b in blocks if not b['closed']]
    openers = {b['line'] for b in blocks}
    for number, line in enumerate(raw.splitlines(), 1):
        if number in openers:
            continue
        candidate = line
        # Diagnose legal but unsupported alternating/nested container prefixes.
        # This is only detection; never reinterpret their content as checked code.
        while True:
            previous = candidate
            candidate, _ = unquote(candidate)
            marker = LIST.match(candidate)
            if marker:
                candidate = marker[3]
            if candidate == previous:
                break
        match = re.fullmatch(r'\s*(`{3,}|~{3,})(.*)', candidate)
        if not match or fence_language(match[2]) not in languages:
            continue
        containing = next((b for b in blocks if b['line'] < number <= b['end_line']), None)
        if containing:
            if containing['lang'] in PLC_LANGS or len(match[1]) < len(containing['delimiter']):
                continue
            errors.append(f'L{number} PLC 围栏被外层围栏吞没；请用更长外层围栏')
        else:
            errors.append(f'L{number} PLC 围栏格式非法或容器缩进不受支持；请用空格列表缩进或移至顶层')
    return errors
