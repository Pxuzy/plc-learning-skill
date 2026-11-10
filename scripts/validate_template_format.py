#!/usr/bin/env python3
"""检查模板资产格式；不证明PLC语义、源码保真或生成文档质量。"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from markdown_fences import body_view, parse_fences
from validate_template_index import table_rows, REGISTRY_HEADING, validate_text

ROOT = Path(__file__).resolve().parents[1]


def heading_text(text):
    """只忽略空白和结尾装饰表情，不用前缀匹配吞掉改名。"""
    return re.sub(r'[\s\U0001F000-\U0001FFFF\u2600-\u27bf\ufe0f]+$', '', text)


def without_comments(text):
    """屏蔽HTML注释但保留物理行号，隐藏文字不构成正文。"""
    return re.sub(r'<!--.*?(?:-->|\Z)',
                  lambda m: ''.join(c if c in '\r\n' else ' ' for c in m[0]),
                  text, flags=re.DOTALL)


def prose_view(text):
    return body_view(without_comments(text))


def validate(root: Path) -> dict:
    root = root.resolve()
    errors = []
    checked = 0

    def issue(path, rule, detail, line=0):
        errors.append({'file': path, 'line': line, 'rule': rule, 'detail': detail})

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
        blocks = parse_fences(without_comments(raw))
        for b in blocks:
            if not b['closed']:
                issue(name, 'fence', '围栏未闭合', b['line'])
        mode = entry.get('view')
        if mode == 'markdown-fences':
            selected = [b for b in blocks if b['lang'] in {'markdown', 'md'}]
            if not selected:
                issue(name, 'copyable-body', '缺少可复制Markdown骨架')
            views = [(prose_view(b['text']), b['line']) for b in selected]
        elif mode == 'body':
            views = [(prose_view(raw), 0)]
        else:
            issue(name, 'contract-schema', 'view仅允许body或markdown-fences')
            continue
        view = '\n'.join(v for v, _ in views)
        if entry['id'] == 'CODE@1.0':
            nested = [b for outer in blocks if outer['lang'] in {'markdown', 'md'}
                      for b in parse_fences(outer['text']) if b['lang'] in {'st', 'scl'}]
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
        for field in entry.get('fields', []):
            if field not in view:
                issue(name, 'field-contract', '缺少必填字段：'+field)
            else:
                for i, line in enumerate(view.splitlines(), 1):
                    if line.startswith(field) and field.endswith('：') and not line[len(field):].strip():
                        following = next((l.strip() for l in view.splitlines()[i:] if l.strip()), '')
                        if not following.startswith(('- ', '* ')):
                            issue(name, 'empty-field', '必填字段缺少说明或占位值：'+field, i)
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
    for path in (root / 'templates').glob('*.md'):
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
