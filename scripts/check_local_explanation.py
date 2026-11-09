#!/usr/bin/env python3
"""B 局部讲解门禁：结构/原码确定性检查；正文覆盖和语义明确标为待审。

python3 -B scripts/check_local_explanation.py 文档.md --source 原始.st
源码物理字符（包括 CRLF/LF、末行换行）原样串接，不做 strip/换行归一。
源末行无换行时，仅在最后源码围栏后紧邻写 <!-- source-eof: none -->，
移除该围栏为闭合所需的一个换行；其余字符一律参与比较。
"""
from __future__ import annotations
import argparse
from pathlib import Path
import re
from block_layout import check_block_layout, modules, field
from check_plc_comments import lex_lines, logical_units, CLOSE
from markdown_fences import PLC_LANGS, ST_LANGS, parse_fences, body_view, fence_diagnostics
from local_explanation_contract import BLOCK_PARTS, SECTION_FIELDS, field_pattern, prose_content

EMOJI = re.compile(r'[\U0001F300-\U0001FAFF\u2600-\u27BF]')
COVERAGE = re.compile(r'(?m)^<!-- (explanation|unreviewed): L(\d+)-L(\d+) -->[ \t]*\r?$')
COVERAGE_CANDIDATE = re.compile(r'(?m)^[ \t]*(?:>[ \t]*)?<!--[ \t]*(?:explanation|unreviewed)\b[^\r\n]*')


def original_source(raw: str) -> tuple[str, list[str]]:
    """直接取物理源码行；共享解析器负责围栏边界，不重建或归一字符。"""
    errors = []; chunks = []
    lines = raw.splitlines(keepends=True)
    blocks = [block for block in parse_fences(raw) if block['lang'] in PLC_LANGS]
    prose = body_view(raw)
    eof = list(re.finditer(r'(?m)^<!-- source-eof: none -->[ \t]*\r?$', prose))
    if len(eof) > 1:
        errors.append('源码末尾换行标记重复')
    for index, block in enumerate(blocks):
        if block['lang'] not in ST_LANGS:
            errors.append('B --source ST 入口不能用其他 PLC 语言替代 ST 源码')
        if block['quote_depth'] or block['list_indent']:
            errors.append('原样源码请使用顶层围栏；不能去掉引用/列表前缀后冒称逐字符一致')
        chunk = ''.join(lines[block['line']:block['end_line']-1])
        if index == len(blocks)-1 and eof:
            following = lines[block['end_line']] if block['end_line'] < len(lines) else ''
            if following.rstrip(' \t\r\n') != '<!-- source-eof: none -->':
                errors.append('源码末尾换行标记须紧邻最后源码围栏之后')
            if chunk.endswith('\r\n'):
                chunk = chunk[:-2]
            elif chunk.endswith('\n'):
                chunk = chunk[:-1]
            else:
                errors.append('源码末尾换行标记缺少可移除的围栏边界换行')
        chunks.append(chunk)
    if not blocks:
        errors.append('缺少原始 ST 源码围栏')
    return ''.join(chunks), errors


def coverage_review(raw: str, source: str, required: bool = True) -> tuple[list[str], list[str]]:
    """仅查源范围映射及非空正文，绝不把标签/词命中当语义证明。"""
    errors = []; pending = []
    prose = body_view(raw)
    for match in COVERAGE_CANDIDATE.finditer(prose):
        if not COVERAGE.fullmatch(match[0]):
            errors.append('覆盖标记格式无效：'+match[0].strip())
    validated_markers = 0
    lexed, lex_errors = lex_lines(source)
    errors.extend('源码词法：'+item for item in lex_errors)
    required_lines = {i for i,line in enumerate(lexed,1)
                if any(not CLOSE.fullmatch(line['mask'][a:b]) for a,b in logical_units(line['mask']))}
    mapped = set(); unreviewed = set(); first_source_line = 1
    for mid, body, _, level in modules(raw):
        view = body_view(body)
        overall = re.search(rf'(?ms)^#{{{level+1}}}\s+{re.escape(BLOCK_PARTS[2])}[^\n]*\n(.*?)(?=^#{{{level+1}}}\s+|\Z)',view)
        module_blocks = [b for b in parse_fences(body) if b['lang'] in PLC_LANGS]
        count = sum(len(b['source_lines']) for b in module_blocks)
        last_source_line = first_source_line + count - 1
        if overall:
            section = overall[1]
            for match in COVERAGE.finditer(section):
                validated_markers += 1
                kind, start, end = match[1], int(match[2]), int(match[3])
                # 标记后的第一段就是对应说明；空标记不能借用后面的其他字段。
                tail = section[match.end():]
                if tail.startswith('\r\n'): tail=tail[2:]
                elif tail.startswith('\n'): tail=tail[1:]
                paragraph = re.split(r'\r?\n\s*\r?\n',tail,1)[0]
                content = prose_content(paragraph).strip()
                field_labels = tuple(label for labels in SECTION_FIELDS for label in labels) + ('一句话说清',)
                begins_with_contract_field = any(re.match(field_pattern(label), content, re.M) for label in field_labels)
                if (start < first_source_line or end < start or end > last_source_line
                        or not content or begins_with_contract_field or paragraph.lstrip().startswith('<!--')
                        or re.fullmatch(r'\*\*[^*\n]+\*\*[：:]?[ \t]*',content)
                        or content.startswith(('#','|'))):
                    errors.append(f'{mid}覆盖映射 L{start}-L{end} 越界或缺对应正文')
                    continue
                target = unreviewed if kind == 'unreviewed' else mapped
                target.update(range(start,end+1))
        first_source_line = last_source_line + 1
    if validated_markers != len(list(COVERAGE.finditer(prose))):
        errors.append('覆盖标记须位于第3小节代码块整体讲解，不能借其他小节充数')
    missing = sorted(required_lines - mapped - unreviewed)
    if missing and required:
        errors.append('执行说明覆盖缺失；须有对应正文源范围映射或明确未审清单：'+','.join(f'L{i}' for i in missing))
    elif missing:
        pending.append('未启用零基础逐范围覆盖；当前未登记的执行单元仍待审：'+','.join(f'L{i}' for i in missing))
    if unreviewed & required_lines:
        pending.append('未审执行说明：'+','.join(f'L{i}' for i in sorted(unreviewed & required_lines)))
    pending.append('所有映射说明的作用/条件/结果、概念首次解释、假设就地限定、单因素反例和时间/跨调用轨迹，均待独立语义审查；范围映射不证明讲解正确或读者已理解')
    return errors, pending


def check_text(raw: str, source: str, allow_ai_tails: bool = False) -> dict:
    errors = fence_diagnostics(raw)
    errors.extend(check_block_layout(raw,mode='local'))
    prose = body_view(raw)
    headings = re.findall(r'(?m)^(#{1,6})[ \t]+([^\r\n]+)',prose)
    if sum(len(level)==1 for level,_ in headings) != 1:
        errors.append('局部成品须有且仅有一个 H1 标题')
    previous = 0
    for level,title in headings:
        if previous and len(level)>previous+1: errors.append('标题层次跳级：'+title)
        previous=len(level)
        if not EMOJI.search(title): errors.append('标题缺少语义表情：'+title)
    items = list(modules(raw))
    if len(items)!=1:
        errors.append('B 单次讲解须且仅含一个 Mxx 模块；分段交付逐段重验')
    before = prose[:items[0][2]] if items else prose
    for label in ('工程','讲解深度','讲解版式','模块编号'):
        values = re.findall(rf'(?m)^> {label}：[ \t]*(\S[^\r\n]*)$',before)
        if len(values)!=1: errors.append('B 元信息缺失、为空或重复：'+label)
        elif label=='讲解版式' and values[0]!='块级': errors.append('B 元信息讲解版式须为块级')
    for mid,body,_,_ in items:
        for label in ('一句话说清','来源定位'):
            content = prose_content(body)
            if len(re.findall(field_pattern(label),content,re.M))!=1 or not field(content,label):
                errors.append(f'{mid}缺少或重复实质字段：{label}')
    extracted, source_errors = original_source(raw)
    errors.extend(source_errors)
    if allow_ai_tails and extracted != source:
        # Compare against each exact source line, never split on an author's
        # existing marker or on // inside a string. Only an appended tail is legal.
        actual = extracted.splitlines(keepends=True)
        expected = source.splitlines(keepends=True)
        restored = []
        if len(actual) == len(expected):
            for got, original in zip(actual, expected):
                if got == original:
                    restored.append(original)
                    continue
                ending = '\r\n' if original.endswith('\r\n') else '\n' if original.endswith('\n') else ''
                body = original[:-len(ending)] if ending else original
                got_body = got[:-len(ending)] if ending and got.endswith(ending) else got
                prefix = body + ' // AI: '
                got_ending = '\r\n' if got.endswith('\r\n') else '\n' if got.endswith('\n') else ''
                if got_ending == ending:
                    if got_body.startswith(prefix) and got_body[len(prefix):].strip():
                        restored.append(original)
                        continue
                break
            if len(restored) == len(expected):
                extracted = ''.join(restored)
    if not source: errors.append('原始源码为空，不能验收')
    if extracted != source:
        different = next((i for i,(a,b) in enumerate(zip(extracted,source)) if a!=b),min(len(extracted),len(source)))
        errors.append(f'源码逐字符不一致：首个差异位置 {different}；输出 {len(extracted)} 字符 / 输入 {len(source)} 字符；不归一空白或末尾换行')
    header = prose[:items[0][2]] if items else prose
    depth = re.findall(r'(?m)^> 讲解深度：[ \t]*(.+)$', header)
    readers = re.findall(r'(?m)^> 读者：[ \t]*(.+)$', header)
    beginner_markers = ('零基础','新手','初学者')
    required_coverage = any(any(term in value for term in beginner_markers) for value in depth + readers)
    coverage_errors, pending = coverage_review(raw,source,required=required_coverage)
    errors.extend(coverage_errors)
    return {'errors':errors,'pending':pending}


def main(argv: list[str] | None = None) -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('document',type=Path)
    ap.add_argument('--source',required=True,type=Path)
    ap.add_argument('--allow-ai-tails',action='store_true',help='仅允许完整原始行之后追加非空 // AI: 尾注；逐行核对原码前缀与换行')
    args=ap.parse_args(argv)
    try:
        result=check_text(args.document.read_bytes().decode('utf-8'),args.source.read_bytes().decode('utf-8'),allow_ai_tails=args.allow_ai_tails)
    except (OSError,UnicodeError) as exc:
        print('ERROR 读取输入失败：'+str(exc));return 1
    for error in result['errors']: print('ERROR '+error)
    for pending in result['pending']: print('待审 '+pending)
    if result['errors']: return 1
    print('结构/源码检查通过；语义未签字，不能据此声称教学验收完成。')
    return 0


if __name__=='__main__': raise SystemExit(main())
