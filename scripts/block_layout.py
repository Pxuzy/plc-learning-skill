# 代码块整体讲解版式检查（供 validate_handbook.py 调用）。
from __future__ import annotations
import re
from markdown_fences import body_view, parse_fences
from check_plc_comments import PLC_LANGS

from local_explanation_contract import (BLOCK_PARTS, MIN_EXECUTIONS, VARIABLE_COLUMNS,
    check_table, check_terminal, check_local_sections, execution_count, prose_content, tables, field_pattern)

# 仅筛选明确空话及格式；通过不证明事实、必要性或因果正确。
VAGUE_PHRASES=('执行判断','执行if判断','执行条件判断','满足条件则赋值','条件很重要','变量变化了',
               '详见代码','见源码','按照控制目标','按控制目标','根据控制目标','根据需求',
               '同上','略述','简单处理','进行相应处理','执行相应操作')
# 占位符不等于诚实未知：仅给“无/未知/待补”而没有判断对象或依据，仍属空话。
BARE_PLACEHOLDERS=frozenset({'无','未知','待补','同前','见上','未分析','待定','略','—'})
SEG_MAX=25    # 单个教学代码块上限（正常按逻辑 3~8 行；超过即"一次一大段"）
# 单一闭合结构（一个 IF/CASE/FOR/WHILE 及其全部嵌套）无法按功能拆开而不重复包裹语句；
# 规范要求这种结构完整保留一次、再按分支锚点讲解，因此不受逐段行数上限约束。
STRUCT_OPEN=('IF','CASE','FOR','WHILE','REPEAT')
STRUCT_CLOSE={'IF':'END_IF','CASE':'END_CASE','FOR':'END_FOR','WHILE':'END_WHILE','REPEAT':'END_REPEAT'}
BRANCH_LABEL=re.compile(r'(?:分支|第[^\]]*(?:步|段)|CASE|状态)',re.I)
HANDBOOK_PARTS = (
    '1. 功能定位与执行条件', '2. 源码', '3. 代码块整体讲解',
    '4. 形象示例', '5. 程序交互与段间交接',
)
# 因果线索筛查：缺少时提示人工核对；命中不构成第一性原理的语义证明。
REASON_MARKERS=('因为','因此','所以','否则','若','如果','才能','必须','避免','防止','保证',
                '代价','后果','不等于','会导致','目的是','为了','必要性','一旦','只要')


def lacks_reasoning(text: str) -> bool:
    """仅检测因果线索，未知/证据不足为合法边界，仍需独立语义审查。"""
    return not any(m in text for m in REASON_MARKERS + ('未知','证据不足','不足以确认'))


def vague_reason(text: str) -> str:
    """返回空话原因；空字符串表示通过。"""
    cleaned=re.sub(r'[`*_（）()【】\[\]\s、，,。．.]','',text).lower()
    if cleaned in BARE_PLACEHOLDERS:
        return '含空话「无依据占位」'
    if cleaned in ('这样写更好','这样就对了','很好','很重要'):
        return '含空话「无依据评价」'
    for phrase in VAGUE_PHRASES:
        if phrase in cleaned:
            return f'含空话「{phrase}」'
    return ''



def single_closed_structure(src: str) -> bool:
    """整块是否只是一个闭合结构（含全部嵌套），而不是多条语句堆叠。

    只有这种结构才允许超过 SEG_MAX：拆开它必然要重复 IF/END_IF 或复制条件头，
    与“源码原样保留一次”冲突。并列结构、顶层赋值或顶层调用都返回 False。
    """
    depth = 0
    opened = None
    for raw in src.splitlines():
        line = re.sub(r'//.*$', '', raw).strip()
        if not line:
            continue
        head = re.match(r'([A-Za-z_]+)', line)
        word = head.group(1).upper() if head else ''
        if word in STRUCT_OPEN:
            if depth == 0:
                if opened is not None:
                    return False
                opened = word
            depth += 1
        elif word.startswith('END_'):
            depth -= 1
            if depth < 0:
                return False
            if depth == 0 and (opened is None or word != STRUCT_CLOSE.get(opened)):
                return False
        elif depth == 0:
            return False
    return opened is not None and depth == 0


def branch_navigation_count(text: str) -> int:
    """Count distinct, existing anchors whose link labels identify branches/steps."""
    anchors=set(re.findall(r'<a\s+id=["\']([^"\']+)["\']\s*>',text,re.I))
    targets={target for label,target in re.findall(r'\[([^\]]+)\]\(#([^)]+)\)',text)
             if BRANCH_LABEL.search(label) and target in anchors}
    return len(targets)


def uses_block_layout(raw: str) -> bool:
    prose=body_view(raw)
    return bool(re.search(r'讲解版式：\s*块级|\b(?:HBK|FB|ST)@3\.0\b|(?m:^#{3,5}\s+3\. 代码块整体讲解)',prose))


def modules(raw: str, mode: str = "auto"):
    prose=body_view(raw)
    handbook = mode == "handbook" or (mode == "auto" and "文档类型：handbook" in prose)
    identifier = r'(?:M\d{2,}|B\d{1,})' if handbook else r'M\d{2,}'
    matches=list(re.finditer(rf'(?m)^(#{{3,4}})\s+({identifier})\s+[^\n]+$',prose))
    for match in matches:
        level=len(match[1])
        tail=prose[match.end():]
        stop=re.search(rf'(?m)^#{{1,{level}}}\s+',tail)
        end=match.end()+stop.start() if stop else len(raw)
        yield match[2],raw[match.start():end],match.start(),level


def field(text: str,label: str) -> str:
    """取加粗字段的实义内容：从字段行起，直到下一个加粗字段、标题或表格。"""
    lines=text.splitlines()
    for i,line in enumerate(lines):
        # 允许字段名后带括号注释，如 **关键逻辑**（为什么只检测一次）：
        m=re.match(rf'\*\*{re.escape(label)}\*\*(?:[（(][^）)\n]*[）)])?[ \t]*[：:][ \t]*(.*)$',line)
        if not m:continue
        parts=[m[1].strip()];fenced=[]
        in_fence=False
        for nxt in lines[i+1:]:
            if nxt.lstrip().startswith('```'):
                in_fence=not in_fence
                continue
            if in_fence:
                # 代码内的注释也是作者写的解释，正文为空时用它兜底。
                stripped=nxt.strip()
                if stripped.startswith(('//','(*','*','// ')):
                    fenced.append(re.sub(r'^(?://|\*|\(\*)+\s*','',stripped))
                continue
            if re.match(r'\*\*[^*\n]+\*\*(?:[（(][^）)\n]*[）)])?[ \t]*[：:]',nxt):break
            if re.match(r'#{1,6}\s',nxt):break
            if nxt.lstrip().startswith('|'):break
            parts.append(nxt.strip())
        prose=' '.join(p for p in parts if p).strip()
        return prose or ' '.join(f for f in fenced if f).strip()
    return ''


def data_rows(text: str,required_header: str='') -> list[str]:
    active=False;rows=[]
    for line in text.splitlines():
        if not line.lstrip().startswith('|'):
            active=False
            continue
        cells=[c.strip() for c in line.strip().strip('|').split('|')]
        if all(re.fullmatch(r':?-+:?',c or 'x') for c in cells):continue
        if (required_header and any(c == required_header or c == required_header+'名称' for c in cells)) or (not required_header and not active):
            active=True
            continue
        if active and any(c for c in cells):rows.append(line)
    return rows


def check_block_layout(raw: str, mode: str = "auto") -> list[str]:
    errors=[];prose=body_view(raw)
    if mode not in ("auto", "local", "handbook"):
        raise ValueError("mode 须为 auto/local/handbook")
    local = mode == "local" or (mode == "auto" and "讲解深度：" in prose
                                and "文档类型：handbook" not in prose)
    # 仅约束成稿边界，不将标题通过当作语义正确。
    leading=raw.lstrip('\ufeff\r\n\t ')
    document_first=leading.splitlines()[0] if leading else ''
    if not re.match(r'^#\s+\S',document_first):
        errors.append('正式稿须以独立 H1 标题开始；请将对话、修改说明和执行前言留在交付消息中')
    blocks=[b for b in parse_fences(raw) if b['lang'] in PLC_LANGS]
    items=list(modules(raw, mode=mode))
    first=blocks[0]['line'] if blocks else None
    before='\n'.join(raw.splitlines()[:first-1]) if first else raw
    if not data_rows(before,'变量'):
        errors.append('块级版式：源码前缺少有实际内容的关键变量介绍表')
    if local:
        pre_module=raw[:items[0][2]] if items else raw
        pre_tables=[(header,rows) for header,rows in tables(prose_content(pre_module)) if VARIABLE_COLUMNS[0] in header]
        if len(pre_tables)!=1:
            errors.append('局部关键变量表必须在模块标题之前且只出现一次')
        errors.extend(check_table(prose_content(pre_module), VARIABLE_COLUMNS, "关键变量表"))
        errors.extend(check_terminal(raw))
    if blocks and not items:errors.append('块级版式：有PLC源码但没有Mxx模块正文')
    owned=[]
    handbook = mode == "handbook" or (mode == "auto" and "文档类型：handbook" in prose)
    for mid,body,start,level in items:
        # 按行号切段：body_view 只用于屏蔽围栏内容，字符偏移不参与切片。
        raw_lines=body.splitlines()
        mask_lines=body_view(body).splitlines()
        if len(mask_lines)!=len(raw_lines):mask_lines=raw_lines
        local_errors=[]
        parts = HANDBOOK_PARTS if handbook else BLOCK_PARTS
        heading_lines=[]  # (line_index, title)
        for title in parts:
            # 允许标题末尾带表情（PLC-TITLE-EMOJI），否则"表情全覆盖"与结构校验互斥。
            _emoji_tail=r'[\U0001F300-\U0001FAFF\u2600-\u27BF\ufe0f\u20e3]*'
            hits=[i for i,line in enumerate(mask_lines)
                  if re.fullmatch(rf'#{{{level+1}}}\s+{re.escape(title)}\s*{_emoji_tail}\s*',line)]
            if len(hits)!=1:local_errors.append(f'{mid}缺少或重复小节：{title}')
            heading_lines.append((hits[0] if len(hits)==1 else None,title))
        view='\n'.join(mask_lines)
        if re.search(r'(?m)^(?:#{1,6}\s+|\*\*)(?:\d+\.\s*)?(?:逐句看|逐行讲解|逐句说明)(?:\*\*)?\s*$',view):
            local_errors.append(f'{mid}正文仍使用逐行讲解；请保留行内注释并改用代码块整体讲解')
        if any(h is None for h,_ in heading_lines):
            errors.extend(local_errors);continue
        positions=[h for h,_ in heading_lines]
        if positions!=sorted(positions):
            local_errors.append(f'{mid}五部分顺序错误：功能与条件→源码→整体讲解→示例→交互')
            errors.extend(local_errors);continue
        sections=[]
        for i,(h,_) in enumerate(heading_lines):
            end=heading_lines[i+1][0] if i<4 else len(raw_lines)
            sections.append('\n'.join(raw_lines[h+1:end]))
        if local:
            local_errors.extend(check_local_sections(sections))
            body_view_text=body_view(body)
            one_liners=list(re.finditer(field_pattern('一句话说清'), body_view_text, re.M))
            first_part=re.search(rf'(?m)^#{{{level+1}}}\s+1\.', body_view_text)
            module_heading=re.match(r'#{3,4}[^\n]*',body_view_text)
            if (len(one_liners)!=1 or first_part is None or module_heading is None
                    or one_liners[0].start() <= module_heading.end()
                    or one_liners[0].start() >= first_part.start()):
                local_errors.append(f'{mid}一句话说清须恰一次且位于模块标题与第1小节之间')
        intro,source,overall,example,interaction=sections
        for label in ('功能定位','代码职责','设计依据'):
            value=field(prose_content(intro),label)
            if not value:local_errors.append(f'{mid}缺少实质内容：{label}')
            elif (why:=vague_reason(value)):local_errors.append(f'{mid}「{label}」{why}；请写清事实、条件必要性与后果')
            elif label=='设计依据' and lacks_reasoning(value):
                local_errors.append(f'{mid}「设计依据」只有描述没有推导：请人工核对事实、约束与条件作用（关键词不是语义证明）')
        if not data_rows(body_view(intro),'进入条件'):local_errors.append(f'{mid}进入条件表为空或缺失')
        srcblocks=[b for b in parse_fences(source) if b['lang'] in PLC_LANGS]
        if not srcblocks:local_errors.append(f'{mid}源码小节缺少PLC源码；仅摘要不得登记已讲')
        # 分段交付：一次只讲一小段，不把整块贴完再集中解释。
        nav=branch_navigation_count(view)
        for b in srcblocks:
            size=b['end_line']-b['line']-1
            if size<=SEG_MAX:
                continue
            # 单一闭合结构保留完整源码一次、按分支锚点讲解，不算“一次一大段”；
            # 但必须真的给出分支导航（至少两处锚点/锚点链接），否则仍按超限拒绝。
            if single_closed_structure(b['text']) and nav>=2:
                continue
            local_errors.append(f'{mid}代码块 {size} 行超过 {SEG_MAX} 行上限：严禁删除、截短或用省略号代替源码；'
                                f'按逻辑边界拆成多段，每段后紧邻讲解再放下一段；单一闭合结构无法拆分时，'
                                f'保留完整源码一次并至少给出两处分支锚点导航')
        for label in ('处理过程','关键逻辑','写法好处','状态变化'):
            value=field(prose_content(overall),label)
            if not value:local_errors.append(f'{mid}整体讲解缺少实质内容：{label}')
            elif (why:=vague_reason(value)):local_errors.append(f'{mid}「{label}」{why}；请写清输入→判断→结果与必要性')
            elif label=='关键逻辑' and lacks_reasoning(value):
                local_errors.append(f'{mid}「关键逻辑」只有描述没有推导：请人工核对单因素删改后果及必要性边界（关键词不是语义证明）')
        for label in ('场景设定','初始状态'):
            value=field(prose_content(example),label)
            if not value:local_errors.append(f'{mid}形象示例缺少：{label}')
            elif (why:=vague_reason(value)):local_errors.append(f'{mid}「{label}」{why}；请写具体变量与初值')
        if execution_count(example) < MIN_EXECUTIONS:
            local_errors.append(f'{mid}形象示例至少 {MIN_EXECUTIONS} 个不同执行序号或时刻标签；时序与因果正确性仍须语义审查')
        if local:
            for section, label in ((example, '理解要点'), (interaction, '交接要点')):
                if not field(prose_content(section), label):
                    local_errors.append(f'{mid}缺少实质内容：{label}')
        if not data_rows(body_view(interaction),'关系'):local_errors.append(f'{mid}程序交互表为空或缺失；无证据也要明确未知')
        for b in parse_fences(body):
            if b['lang'] in PLC_LANGS:
                # Bind every source fence to a real module, not a heading token elsewhere.
                absolute=raw[:start].count('\n')+b['line']
                owned.append(absolute)
        errors.extend(local_errors)
    if items and blocks:
        actual={b['line'] for b in blocks}
        if set(owned)!=actual:errors.append('块级版式：存在未归属模块的PLC代码块')
    return errors
