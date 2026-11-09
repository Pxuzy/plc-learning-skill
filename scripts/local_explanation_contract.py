"""模式 B 的小型共享契约；只检查可确定的结构，不评判 PLC 语义。"""
from __future__ import annotations
import re
from markdown_fences import body_view

BLOCK_PARTS = ('1. 功能定位与执行条件', '2. 源码', '3. 代码块整体讲解',
               '4. 形象示例', '5. 程序交互与段间交接')
SECTION_FIELDS = (('功能定位', '代码职责', '设计依据'), ('来源定位',),
                  ('处理过程', '关键逻辑', '写法好处', '状态变化'),
                  ('场景设定', '初始状态', '理解要点'), ('交接要点',))
VARIABLE_COLUMNS = ('变量', '数据类型', '方向', '含义', '谁写谁读', '证据等级')
CONDITION_COLUMNS = ('进入条件', '成立时', '不成立时', '依据')
EXECUTION_COLUMNS = ('阶段/执行', '输入与原状态', '本段处理', '执行结果')
INTERACTION_COLUMNS = ('关系', '来源', '目标', '关联变量', '实际作用')
MIN_EXECUTIONS = 3
END_MARKER = '<!-- 本段已完 -->'
TERMINAL = re.compile(r'<!--\s*(?:本段已完|继续点[：:]\s*M\d{2,}\s+[^<>\n]+?)\s*-->')


def field_pattern(label: str) -> str:
    return rf'^\*\*{re.escape(label)}\*\*(?:[（(][^）)\n]*[）)])?[ \t]*[：:]'


def prose_content(raw: str) -> str:
    """源码及 HTML 元注释均不能兜底充当正文解释。"""
    return re.sub(r'<!--.*?-->', '', body_view(raw), flags=re.S)


def tables(text: str) -> list[tuple[list[str], list[list[str]]]]:
    result = []; group = []
    for line in body_view(text).splitlines() + ['']:
        if line.strip().startswith('|') and line.strip().endswith('|'):
            group.append([cell.strip() for cell in line.strip().strip('|').split('|')])
            continue
        if len(group) >= 2 and all(re.fullmatch(r':?-{3,}:?', cell) for cell in group[1]):
            result.append((group[0], group[2:]))
        group = []
    return result


def check_table(text: str, columns: tuple[str, ...], label: str) -> list[str]:
    found = [(header, rows) for header, rows in tables(text) if columns[0] in header]
    if len(found) != 1:
        return [f'{label}须有且仅有一张表（列：{"、".join(columns)}）']
    header, rows = found[0]
    errors = []
    if header != list(columns):
        errors.append(f'{label}列须完整且按序：{"、".join(columns)}')
    if not rows or any(len(row) != len(columns) or any(not cell for cell in row) for row in rows):
        errors.append(f'{label}数据行及必要单元格不得为空、列数须一致')
    return errors


def execution_rows(text: str) -> list[list[str]]:
    """只计执行表里带唯一序号或时刻标签的数据行。"""
    return [row for header, rows in tables(text)
            if header and re.fullmatch(r'阶段[/／](?:执行|扫描)', header[0])
            for row in rows if row and (re.search(r'第\s*[0-9一二三四五六七八九十]+\s*次', row[0])
                                       or re.search(r'\d+\s*ms\b', row[0], re.I))]


def execution_count(text: str) -> int:
    rows = execution_rows(text)
    tracks: dict[str, dict[str, set[int]]] = {}
    digits = {char: number for number, char in enumerate('一二三四五六七八九', 1)}
    for row in rows:
        ordinal = re.search(r'第\s*([0-9一二三四五六七八九十]+)\s*次', row[0])
        moment = re.search(r'(\d+)\s*ms\b', row[0], re.I)
        track = re.match(r'\s*(.*?)\s*(?=第\s*[0-9一二三四五六七八九十]+\s*次|\d+\s*ms\b)', row[0], re.I)
        name = re.sub(r'\s+', '', track[1]).upper() if track and track[1].strip() else ''
        values = tracks.setdefault(name, {'ordinal': set(), 'time': set()})
        if ordinal:
            token = ordinal[1]
            if token.isdecimal():
                values['ordinal'].add(int(token))
            elif re.fullmatch(r'(?:[一二三四五六七八九]?十[一二三四五六七八九]?|[一二三四五六七八九])', token):
                head, _, tail = token.partition('十')
                number = (digits.get(head, 1)*10 + digits.get(tail, 0)) if '十' in token else digits[token]
                values['ordinal'].add(number)
        elif moment:
            values['time'].add(int(moment[1]))
    return min((len(values['ordinal'] or values['time']) for values in tracks.values()), default=0)


def check_terminal(raw: str) -> list[str]:
    prose = body_view(raw)
    matches = list(TERMINAL.finditer(prose))
    candidates = re.findall(r'<!--[^>]*(?:本段已完|继续点)[^>]*-->', prose)
    if len(matches) != 1 or len(candidates) != 1 or prose[matches[0].end():].strip():
        return ['局部结束标记须恰一且位于文末：<!-- 本段已完 --> 或 <!-- 继续点：M02 实际模块名 -->']
    return []


def check_local_sections(sections: list[str]) -> list[str]:
    """与两份骨架一致的字段/表格定义；由实际块级检查器调用。"""
    errors = []
    for section, labels in zip(sections, SECTION_FIELDS):
        prose = prose_content(section)
        for label in labels:
            if len(re.findall(field_pattern(label), prose, flags=re.M)) != 1:
                errors.append(f'局部字段「{label}」须存在且恰一次')
    errors.extend(check_table(sections[0], CONDITION_COLUMNS, '进入条件表'))
    errors.extend(check_table(sections[3], EXECUTION_COLUMNS, '执行示例表'))
    errors.extend(check_table(sections[4], INTERACTION_COLUMNS, '程序交互表'))
    return errors
