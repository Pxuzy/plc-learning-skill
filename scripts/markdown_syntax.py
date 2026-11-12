#!/usr/bin/env python3
"""Markdown syntax and rendered-node checks (CommonMark + pipe tables).

Requires markdown-it-py>=3,<5; absence is a validation blocker, never a pass.
"""
from __future__ import annotations
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit
from markdown_fences import body_view, fence_diagnostics, unquote as strip_quote


def parser():
    try:
        from markdown_it import MarkdownIt
    except ImportError as exc:
        raise RuntimeError('缺少 markdown-it-py：python -m pip install "markdown-it-py>=3,<5"；未执行渲染验收') from exc
    return MarkdownIt('commonmark').enable('table')


def cells(line):
    """Use the renderer's escape semantics, including pipes inside backticks."""
    from markdown_it.rules_block.table import escapedSplit
    result = escapedSplit(line.strip())
    if result and result[0] == '':
        result.pop(0)
    if result and result[-1] == '':
        result.pop()
    return [value.strip() for value in result]


def slug(title):
    title = re.sub(r'<[^>]+>', '', title).lower()
    return re.sub(r'[^\w\-\s]', '', title).strip().replace(' ', '-')


def anchors(tokens, text):
    result = re.findall(r'<a\s+(?:[^>]*?\s)?(?:id|name)=["\']([^"\']+)["\']', body_view(text), re.I)
    seen = {}
    for i, token in enumerate(tokens):
        if token.type == 'heading_open' and i + 1 < len(tokens):
            key = slug(tokens[i + 1].content)
            number = seen.get(key, 0)
            seen[key] = number + 1
            result.append(key if not number else f'{key}-{number}')
    return result


def inspect_markdown(text: str, path: Path | None = None, strict=False, check_links=True):
    md = parser()
    env = {}
    tokens = md.parse(text, env)
    lines = text.splitlines()
    issues = []
    def issue(line, rule, detail, severity='error'):
        item = {'line': line, 'rule': rule, 'detail': detail, 'severity': severity}
        if item not in issues:
            issues.append(item)
    for message in fence_diagnostics(text):
        match = re.match(r'L(\d+)', message)
        issue(int(match[1]) if match else 0, 'fence', message)
    excluded = [t.map for t in tokens if t.type in {'fence', 'code_block'} and t.map]
    comments = []
    for match in re.finditer(r'<!--[\s\S]*?-->', text):
        comments.append((text[:match.start()].count('\n'), text[:match.end()].count('\n') + 1))
    frontmatter_end = 0
    if lines and lines[0] == '---':
        frontmatter_end = next((i + 1 for i, value in enumerate(lines[1:], 1) if value == '---'), 0)
    def skipped(index):
        return index < frontmatter_end or any(a <= index < b for a, b in excluded + comments)
    tables = [t.map for t in tokens if t.type == 'table_open' and t.map]
    rows = {t.map[0]: t for t in tokens if t.type == 'tr_open' and t.map}
    table_report = []
    for start, end in tables:
        width = len(cells(strip_quote(lines[start])[0]))
        table_report.append({'line': start + 1, 'end_line': end, 'columns': width,
                             'rows': sum(start <= row < end for row in rows)})
        for index in range(start + 2, end):
            if index not in rows:
                continue
            source = strip_quote(lines[index])[0].strip()
            if '|' not in source:
                issue(index + 1, 'table-absorbed-prose', '普通正文被表格吞入；表后须空行再写正文')
            actual = len(cells(source))
            if actual != width:
                issue(index + 1, 'table-columns', f'表体 {actual} 列与表头 {width} 列不一致；渲染器会截断或补空单元格')
        separator = strip_quote(lines[start + 1])[0]
        if not all(re.fullmatch(r':?-{3,}:?', c) for c in cells(separator)):
            issue(start + 2, 'table-separator', '表格分隔单元至少三个连字符，可带对齐冒号')
        if strict and start and lines[start - 1].strip():
            issue(start + 1, 'table-spacing', '表格前缺少空行，跨渲染器显示不稳定')
    # Scan every apparent table group, not just recognized header+separator pairs.
    group = []
    for index in range(len(lines) + 1):
        source = strip_quote(lines[index])[0].strip() if index < len(lines) else ''
        candidate = index < len(lines) and not skipped(index) and (source.startswith('|') or source.endswith('|')) and '|' in source
        if candidate:
            group.append(index)
            continue
        if group:
            missing = [i for i in group if not any(a <= i < b for a, b in tables)]
            if missing:
                issue(missing[0] + 1, 'table-unrendered', '疑似表格未生成 table 节点：检查表头、紧邻分隔行、空行及 HTML 容器')
            group = []
    loose = []
    for index in range(len(lines) + 1):
        source = strip_quote(lines[index])[0].strip() if index < len(lines) else ''
        plain = re.sub(r'(`+).*?\1', '', source)
        candidate = (index < len(lines) and not skipped(index) and '|' in plain
                     and not lines[index].lstrip().startswith('>')
                     and not source.startswith(('#', '>', '-', '*', '+'))
                     and not any(a <= index < b for a, b in tables))
        if candidate:
            loose.append(index)
        else:
            if len(loose) >= 2:
                issue(loose[0] + 1, 'table-unrendered', '连续管道分列内容未渲染成表格，缺少有效表头或分隔行')
            loose = []
    # Hidden content: unknown HTML placeholder tags disappear in normal viewers.
    allowed = {'a', 'br', 'code', 'kbd', 'sub', 'sup', 'span', 'details', 'summary',
               'em', 'strong', 'div', 'p', 'img', 'table', 'thead', 'tbody', 'tr', 'td', 'th', 'hr'}
    for token in tokens:
        for child in token.children or []:
            if child.type == 'html_inline':
                match = re.match(r'</?([A-Za-z][\w-]*)\b', child.content)
                if match and match[1].lower() not in allowed:
                    issue((token.map or [0])[0] + 1, 'hidden-placeholder',
                          '占位符被解析为 HTML 标签而隐藏；用行内代码或转义尖括号')
    explicit = re.findall(r'<a\s+(?:[^>]*?\s)?(?:id|name)=["\']([^"\']+)["\']', body_view(text), re.I)
    for value in set(explicit):
        if explicit.count(value) > 1:
            issue(0, 'duplicate-anchor', f'显式锚点重复：{value}')
    ids = set(anchors(tokens, text))
    prev_level = 0
    for token in tokens:
        if not token.map or token.type not in {'heading_open', 'bullet_list_open', 'ordered_list_open', 'fence'}:
            continue
        start, end = token.map
        if skipped(start) and token.type != 'fence':
            continue
        if token.type == 'heading_open':
            level = int(token.tag[1])
            if strict and prev_level and level > prev_level + 1:
                issue(start + 1, 'heading-level', f'标题从 H{prev_level} 跳到 H{level}')
            prev_level = level
            if strict and start and lines[start - 1].strip():
                issue(start + 1, 'heading-spacing', '标题前缺少空行')
            if strict and end < len(lines) and lines[end].strip():
                issue(end + 1, 'heading-spacing', '标题后缺少空行')
        elif strict and token.level == 0 and start and lines[start - 1].strip():
            issue(start + 1, 'block-spacing', '列表或代码块前缺少空行')
    if strict:
        for index, line in enumerate(lines):
            if skipped(index):
                continue
            if line.endswith((' ', '\t')) and not line.endswith('  '):
                issue(index + 1, 'trailing-space', '行尾孤立空白；两空格硬换行除外')
            if '\t' in line[:len(line) - len(line.lstrip())]:
                issue(index + 1, 'tab-indent', '正文缩进含制表符，改为空格')
    if check_links:
        for token in tokens:
            if token.type != 'inline':
                continue
            line = (token.map or [0])[0] + 1
            # Mask inline code before searching unresolved reference syntax.
            prose = re.sub(r'(`+).*?\1', '', token.content)
            references = env.get('references', {})
            for match in re.finditer(r'(?<!!)\[([^\]\n]+)\]\[([^\]\n]*)\]', prose):
                label = (match[2] or match[1]).upper()
                label = re.sub(r'\s+', ' ', label).strip()
                if label not in references:
                    issue(line, 'link-reference', f'引用式链接未定义：{label}')
            for child in token.children or []:
                target = child.attrGet('href') if child.type == 'link_open' else child.attrGet('src') if child.type == 'image' else None
                if not isinstance(target, str) or not target:
                    continue
                parts = urlsplit(target)
                if parts.scheme or parts.netloc:
                    continue
                fragment = unquote(parts.fragment)
                if not parts.path:
                    if fragment and fragment not in ids:
                        issue(line, 'link-anchor', f'页内锚点不存在：{fragment}')
                elif path is not None:
                    dest = path.parent / unquote(parts.path)
                    if not dest.exists():
                        issue(line, 'link-path', f'本地链接目标不存在：{parts.path}')
                    elif fragment and dest.suffix.lower() == '.md':
                        other = dest.read_text(encoding='utf-8')
                        if fragment not in anchors(md.parse(other), other):
                            issue(line, 'link-anchor', f'链接目标锚点不存在：{parts.path}#{fragment}')
    return {'issues': issues, 'tables': table_report,
            'rendered_headings': sum(t.type == 'heading_open' for t in tokens),
            'profile': 'CommonMark + pipe tables (markdown-it-py); no editor-specific extensions'}


def main():
    import argparse
    import json
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('root', type=Path)
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()
    root = args.root.resolve()
    paths = [p for p in (root / n for n in ('SKILL.md', 'README.md', 'CHANGELOG.md')) if p.is_file()]
    paths += sorted((root / 'references').rglob('*.md')) + sorted((root / 'templates').rglob('*.md'))
    reports = []
    try:
        for path in paths:
            reports.append({'file': path.relative_to(root).as_posix(),
                            **inspect_markdown(path.read_text(encoding='utf-8'), path, strict=True, check_links=False)})
    except RuntimeError as exc:
        print(str(exc))
        return 2
    if not paths:
        print('ERROR 未找到运行包 Markdown 文件')
        return 1
    result = {'checked_files': len(paths), 'rendered_tables': sum(len(r['tables']) for r in reports),
              'errors': sum(len(r['issues']) for r in reports), 'documents': reports,
              'scope': '运行包 Markdown 严格语法与渲染；链接另由严格技能校验检查；开发测试和历史计划不在此范围'}
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else
          f"Markdown: {result['checked_files']} 文件，{result['rendered_tables']} 张实际表格，{result['errors']} 个错误")
    return int(bool(result['errors']))


if __name__ == '__main__':
    raise SystemExit(main())
