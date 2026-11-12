#!/usr/bin/env python3
"""检查模板资产格式；不证明PLC语义、源码保真或生成文档质量。"""
from __future__ import annotations
import argparse
import json
import re
from collections import Counter
from pathlib import Path
from markdown_fences import body_view, parse_fences, fence_diagnostics
from validate_template_index import table_rows, REGISTRY_HEADING, validate_text

ROOT = Path(__file__).resolve().parents[1]

# 与 scripts/validate_skill.py 的 is_emoji 同一码位集合，另含变体选择符。
DECORATION = r'[\s\U0001F300-\U0001FAFF\u2600-\u27bf\u2b00-\u2bff\ufe0e\ufe0f]+$'
FIELD_LABEL_RE = re.compile(r'^\*\*(.+?)\*\*\s*[：:]')
QUOTE_LABEL_RE = re.compile(r'^>\s*([^：:]+)[：:]')


def heading_text(text):
    """只忽略空白和结尾装饰表情，不用前缀匹配吞掉改名。"""
    from html import unescape
    return re.sub(DECORATION, '', unescape(text))


def field_label(field):
    """契约字段归一为行首标签；块引用字段只比标签，不比占位值。"""
    if field.startswith('> '):
        return '> ' + re.split(r'[：:]', field[2:], 1)[0].strip() + '：'
    return field


def skeleton_labels(view):
    """可复制骨架里行首的契约字段标签：`**字段**：` 与 `> 字段：`；正文夹叙的粗体不算。"""
    labels = set()
    for line in view.splitlines():
        bold = FIELD_LABEL_RE.match(line)
        if bold:
            labels.add('**' + bold[1].strip() + '**：')
            continue
        quote = QUOTE_LABEL_RE.match(line)
        if quote:
            labels.add('> ' + quote[1].strip() + '：')
    return labels


def valid_authority_spec(spec):
    """权威正文结构规格：view、非空headings，可选fields/tables。"""
    if not isinstance(spec, dict) or spec.get('view') not in {'body', 'marked-body'}:
        return False
    headings = spec.get('headings')
    if not isinstance(headings, list) or not headings:
        return False
    if not all(isinstance(h, list) and len(h) == 2 and isinstance(h[0], int) and 1 <= h[0] <= 6
               and isinstance(h[1], str) and h[1] for h in headings):
        return False
    return (isinstance(spec.get('fields', []), list)
            and all(isinstance(v, str) and v for v in spec.get('fields', []))
            and isinstance(spec.get('tables', []), list)
            and all(isinstance(t, list) and t and all(isinstance(v, str) and v for v in t)
                    for t in spec.get('tables', [])))


def table_headers(view):
    """Recognize real Markdown headers by their following delimiter row."""
    lines = view.splitlines()
    headers = []
    for header, delimiter in zip(lines, lines[1:]):
        if not header.strip().startswith('|') or not delimiter.strip().startswith('|'):
            continue
        cells = [c.strip() for c in header.strip().strip('|').split('|')]
        separators = [c.strip() for c in delimiter.strip().strip('|').split('|')]
        if len(cells) == len(separators) and all(re.fullmatch(r':?-{3,}:?', c) for c in separators):
            headers.append(tuple(cells))
    return headers


def heading_issues(heads, spec, rule):
    """按契约核对标题层级、顺序、数量与契约外新增。"""
    problems = []
    last = -1
    for level, text in spec:
        found = [i for i, h in enumerate(heads) if h[0] == level and h[1] == text and i > last]
        if not found:
            problems.append((rule, f'缺失、层级或顺序错误：H{level} {text}'))
        else:
            last = found[0]
    expected = Counter(tuple(h) for h in spec)
    actual = Counter((h[0], h[1]) for h in heads)
    for level, text in sorted(actual - expected):
        problems.append((rule, f'契约外标题：H{level} {text}'))
    for level, text in sorted(expected - actual):
        problems.append((rule, f'标题数量不符：H{level} {text}'))
    return problems


def without_comments(text):
    """屏蔽HTML注释但保留物理行号，隐藏文字不构成正文。"""
    return re.sub(r'<!--.*?(?:-->|\Z)',
                  lambda m: ''.join(c if c in '\r\n' else ' ' for c in m[0]),
                  text, flags=re.DOTALL)


def prose_view(text):
    return body_view(without_comments(text))


def marked_sections(raw):
    """Visible Markdown bodies; HTML boundary markers do not alter rendering."""
    starts = list(re.finditer(r'(?m)^<!-- template-body:start -->\s*$', raw))
    ends = list(re.finditer(r'(?m)^<!-- template-body:end -->\s*$', raw))
    if not starts or len(starts) != len(ends):
        return []
    result = []
    previous = -1
    for start, end in zip(starts, ends):
        if start.start() <= previous or end.start() <= start.end():
            return []
        result.append((raw[start.end():end.start()], raw[:start.end()].count('\n')))
        previous = end.end()
    return result


def validate(root: Path) -> dict:
    root = root.resolve()
    errors = []
    checked = 0

    def issue(path, rule, detail, line=0):
        errors.append({'file': path, 'line': line, 'rule': rule, 'detail': detail})

    def render_checks(name, raw):
        from markdown_syntax import inspect_markdown
        try:
            for item in inspect_markdown(raw, root / name, strict=True, check_links=False)['issues']:
                issue(name, item['rule'], item['detail'], item['line'])
        except RuntimeError as exc:
            issue(name, 'render-dependency', str(exc))
        for message in fence_diagnostics(raw):
            line = re.match(r'L(\d+)', message)
            issue(name, 'fence', message, int(line[1]) if line else 0)
        # Check the actual visible document, not an unwrapped copy of a fence.
        for block in parse_fences(without_comments(raw)):
            content = prose_view(block['text'])
            if (re.search(r'(?m)^#{1,6} ', content)
                    or table_headers(content)):
                issue(name, 'template-render', '模板标题或表格被代码围栏包裹，须改为可渲染正文', block['line'])

    def asset(name):
        if not isinstance(name, str) or Path(name).is_absolute() or '..' in Path(name).parts:
            issue(str(name), 'unsafe-path', '路径须为技能内相对路径')
            return None
        path = root / name
        try:
            path.resolve().relative_to(root)
        except ValueError:
            issue(name, 'unsafe-path', '符号链接越出技能目录')
            return None
        if not path.is_file():
            issue(name, 'missing-file', '缺少登记资产')
            return None
        return path

    index_path = asset('references/template-index.md')
    contract_path = asset('assets/template-format-contracts.json')
    if index_path is None or contract_path is None:
        return {'checked': 0, 'errors': errors}
    try:
        index = index_path.read_text(encoding='utf-8')
        contract = json.loads(contract_path.read_text(encoding='utf-8'))
        if not isinstance(contract, dict) or contract.get('schema') != 1 or not isinstance(contract.get('templates'), list):
            raise ValueError('契约schema或模板集合无效')
    except (ValueError, OSError, UnicodeError) as exc:
        issue('assets/template-format-contracts.json', 'contract-schema', type(exc).__name__)
        return {'checked': 0, 'errors': errors}
    for detail in validate_text(index, root):
        issue('references/template-index.md', 'registry', detail)
    registered = {}
    for row in table_rows(index, REGISTRY_HEADING)[1]:
        if len(row) == 6:
            match = re.fullmatch(r'`([^`]+)`', row[2])
            if match:
                registered[match[1]] = row[0] + '@' + row[1]
    presentation = {}
    for row in table_rows(index, '## 呈现模板登记（局部讲解与导航）')[1]:
        if len(row) != 5:
            issue('references/template-index.md', 'presentation-registry', '呈现登记列数错误')
            continue
        a = re.fullmatch(r'`([^`]+)`', row[1])
        p = re.fullmatch(r'`([^`]+)`', row[2])
        if not a or not p or p[1] in presentation:
            issue('references/template-index.md', 'presentation-registry', '呈现路径重复或无效')
            continue
        presentation[p[1]] = (row[0], a[1])
    if not presentation:
        issue('references/template-index.md', 'presentation-registry', '呈现登记为空')
    expected = {**registered, **{p: v[0] for p, v in presentation.items()}}
    seen = set()
    for entry in contract['templates']:
        if not isinstance(entry, dict) or not isinstance(entry.get('path'), str):
            issue('assets/template-format-contracts.json', 'contract-schema', '每项须含path')
            continue
        if (not isinstance(entry.get('headings'), list) or not entry['headings']
                or not all(isinstance(h, list) and len(h) == 2
                           and isinstance(h[0], int) and 1 <= h[0] <= 6
                           and isinstance(h[1], str) and h[1] for h in entry['headings'])
                or not all(isinstance(entry.get(k), list) and all(isinstance(v, str) and v for v in entry[k])
                           for k in ('fields',))
                or not isinstance(entry.get('tables'), list)
                or not all(isinstance(t, list) and t and all(isinstance(v, str) and v for v in t)
                           for t in entry['tables'])):
            issue(entry['path'], 'contract-schema', '标题、字段、表头规格类型无效或标题为空')
            continue
        name = entry['path']
        if name in seen:
            issue(name, 'contract-schema', '契约重复')
            continue
        seen.add(name)
        authority_spec = entry.get('authority_spec')
        if authority_spec is not None and not valid_authority_spec(authority_spec):
            issue(name, 'contract-schema', 'authority_spec须含view、非空headings与可选fields/tables')
            authority_spec = None
        path = asset(name)
        if path is None:
            continue
        if name not in expected or entry.get('id') != expected[name]:
            issue(name, 'unregistered-template', 'ID或版本与唯一注册表不符')
        try:
            raw = path.read_text(encoding='utf-8')
        except (OSError, UnicodeError):
            issue(name, 'encoding', '模板须为可读UTF-8文本')
            continue
        checked += 1
        declarations = re.findall(r'(?m)^<!-- template-id: (.*?) -->$', raw)
        if declarations != [entry.get('id')]:
            issue(name, 'declaration', '须有且仅有一个匹配ID/版本的声明')
        if name in presentation:
            token, authority = presentation[name]
            if authority == name or authority != entry.get('authority'):
                issue(name, 'compat-authority', '权威路径不得自指，须与已审格式规格中的正文匹配')
            target = asset(authority)
            marker = f'<!-- template-compat: {token} -> {authority} -->'
            if raw.count(marker) != 1:
                issue(name, 'compat-declaration', '兼容呈现须精确标注权威正文')
            if target and not target.read_text(encoding='utf-8').strip():
                issue(authority, 'empty-section', '权威正文为空')
            if target and authority_spec:
                authority_raw = target.read_text(encoding='utf-8')
                render_checks(authority, authority_raw)
                if authority_spec['view'] == 'marked-body':
                    picked = marked_sections(authority_raw)
                    if not picked:
                        issue(authority, 'authority-heading', '权威正文缺少成对模板边界')
                    authority_view = '\n'.join(prose_view(text) for text, _ in picked)
                else:
                    authority_view = prose_view(authority_raw)
                authority_heads = [(len(m[1]), heading_text(m[2])) for m in
                                   re.finditer(r'(?m)^(#{1,6}) (.+?)\s*$', authority_view)]
                for rule, detail in heading_issues(authority_heads, authority_spec['headings'],
                                                   'authority-heading'):
                    issue(authority, rule, detail)
                if 'tables' in authority_spec:
                    wanted = Counter(tuple(t) for t in authority_spec['tables'])
                    actual = Counter(table_headers(authority_view))
                    for table in sorted(wanted - actual):
                        issue(authority, 'authority-table', '权威正文缺少或改写表头：'+' / '.join(table))
                    for table in sorted(actual - wanted):
                        issue(authority, 'authority-table', '权威正文含契约外表：'+' / '.join(table))
                authority_fields = authority_spec.get('fields', [])
                for field in authority_fields:
                    if not any(line.startswith(field) for line in authority_view.splitlines()):
                        issue(authority, 'authority-field', '权威骨架缺少字段：'+field)
                if authority_fields:
                    known = {field_label(f) for f in authority_fields}
                    for label in sorted(skeleton_labels(authority_view) - known):
                        issue(authority, 'authority-field', '权威骨架含契约外字段：'+label)
        blocks = parse_fences(without_comments(raw))
        for b in blocks:
            if not b['closed']:
                issue(name, 'fence', '围栏未闭合', b['line'])
        render_checks(name, raw)
        mode = entry.get('view')
        selected = []
        if mode == 'marked-body':
            selected = marked_sections(raw)
            if not selected:
                issue(name, 'copyable-body', '缺少成对的可渲染模板边界')
            views = [(prose_view(text), offset) for text, offset in selected]
        elif mode == 'body':
            views = [(prose_view(raw), 0)]
        else:
            issue(name, 'contract-schema', 'view仅允许body或marked-body')
            continue
        view = '\n'.join(v for v, _ in views)
        if mode == 'marked-body' and entry.get('fields'):
            nested = [b for text, _ in selected for b in parse_fences(text)
                      if b['lang'] in {'st', 'scl'}]
            if not nested or not all(b['closed'] and b['text'].strip() for b in nested):
                issue(name, 'source-slot', '可复制骨架须保留闭合且非空的ST/SCL源码占位围栏')
        heads = []
        for v, offset in views:
            for i, line in enumerate(v.splitlines(), 1):
                m = re.match(r'^(#{1,6}) (.+?)\s*$', line)
                if m:
                    heads.append((len(m[1]), heading_text(m[2]), offset+i))
            # Reject sections whose whole subtree has no content; child sections may carry it.
            lines = v.splitlines()
            for i, line in enumerate(lines):
                m = re.match(r'^(#{1,6}) ', line)
                if not m:
                    continue
                level = len(m[1]); end = len(lines)
                for j in range(i+1, len(lines)):
                    nxt = re.match(r'^(#{1,6}) ', lines[j])
                    if nxt and len(nxt[1]) <= level:
                        end = j; break
                content = [l for l in lines[i+1:end] if l.strip()
                           and not re.match(r'^#{1,6} ', l) and not l.lstrip().startswith('<!--')]
                if not content:
                    issue(name, 'empty-section', '标题下无正文或子节内容', offset+i+1)
        last = -1
        required = entry.get('headings', [])
        if not required:
            issue(name, 'contract-schema', '必需标题清单不能为空')
        for level, prefix in required:
            matches = [i for i, h in enumerate(heads) if h[0] == level and h[1] == prefix
                       and i > last]
            if not matches:
                issue(name, 'heading-contract', f'缺失、层级或顺序错误：H{level} {prefix}')
            else:
                last = matches[0]
        for level, prefix in {tuple(h) for h in required}:
            expected_count = sum(h == [level, prefix] for h in required)
            actual_count = sum(h[0] == level and h[1] == prefix for h in heads)
            if expected_count != actual_count:
                issue(name, 'heading-contract', f'标题数量不符：H{level} {prefix}')
        # Every registered view has a fixed heading contract, including body views.
        listed = {tuple(h) for h in required}
        for level, text, line in heads:
            if (level, text) not in listed:
                issue(name, 'heading-contract', f'骨架含契约外标题：H{level} {text}', line)
        spec_fields = entry.get('fields', [])
        for field in spec_fields:
            if not any(line.startswith(field) for line in view.splitlines()):
                issue(name, 'field-contract', '缺少必填字段：'+field)
            else:
                for i, line in enumerate(view.splitlines(), 1):
                    if line.startswith(field) and field.endswith('：') and not line[len(field):].strip():
                        following = next((l.strip() for l in view.splitlines()[i:] if l.strip()), '')
                        if not following.startswith(('- ', '* ')):
                            issue(name, 'empty-field', '必填字段缺少说明或占位值：'+field, i)
        if spec_fields:
            # 契约列举了字段即可复制骨架的字段集合须与之一致；正文夹叙的粗体不算字段。
            known = {field_label(f) for f in spec_fields}
            for label in sorted(skeleton_labels(view) - known):
                issue(name, 'field-contract', '可复制骨架含契约外字段：'+label)
        for mapping in entry.get('authority_tables', []):
            authority = presentation.get(name, ('', ''))[1]
            authority_path = asset(authority)
            source_header = mapping['source']
            target_header = mapping['target']
            aliases = mapping['aliases']
            def has_header(text, header):
                return any([c.strip() for c in l.strip().strip('|').split('|')] == header
                           for l in text.splitlines() if l.strip().startswith('|'))
            if (not authority_path or not has_header(prose_view(authority_path.read_text(encoding='utf-8')), source_header)
                    or not has_header(view, target_header) or set(aliases) != set(source_header)
                    or sorted(aliases.values()) != sorted(target_header)):
                issue(name, 'compat-field-map', '兼容表必须完整映射权威列，不得丢失或合并必填字段')
        for table in sorted(Counter(table_headers(view)) - Counter(tuple(t) for t in entry['tables'])):
            issue(name, 'table-contract', '骨架含契约外表：'+' / '.join(table))
        for table in entry.get('tables', []):
            # Exact ordered header; row content is deliberately not a semantic assertion.
            if not any([c.strip() for c in l.strip().strip('|').split('|')] == table
                       for l in view.splitlines() if l.strip().startswith('|')):
                issue(name, 'table-contract', '缺少或改写表头：'+' / '.join(table))
        view_lines = view.splitlines()
        for i, line in enumerate(view_lines):
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if not line.strip().startswith('|') or cells not in entry.get('tables', []):
                continue
            next_cells = ([c.strip() for c in view_lines[i+1].strip().strip('|').split('|')]
                          if i+1 < len(view_lines) else [])
            if len(next_cells) != len(cells) or not all(re.fullmatch(r':?-{3,}:?', c) for c in next_cells):
                issue(name, 'table-structure', '表头后须有同列数的Markdown分隔行', i+1)
    for name in expected.keys() - seen:
        issue(name, 'contract-coverage', '登记模板未覆盖格式契约')
    for path in (root / 'templates').rglob('*.md'):
        rel = path.relative_to(root).as_posix()
        if rel != 'templates/index.md' and rel not in expected:
            issue(rel, 'unregistered-template', '模板文件未登记')
    return {'checked': checked, 'errors': errors}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', nargs='?', type=Path, default=ROOT)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    try:
        report = validate(args.root)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        report = {'checked': 0, 'errors': [{'file': '', 'line': 0, 'rule': 'input',
                                          'detail': type(exc).__name__}]}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for error in report['errors']:
            print(f"ERROR {error['file']}:{error['line']} [{error['rule']}] {error['detail']}")
        print(f"模板格式：已检查 {report['checked']} 份资产，{len(report['errors'])} 个错误；不证明PLC语义")
    return int(bool(report['errors']))


if __name__ == '__main__':
    raise SystemExit(main())
