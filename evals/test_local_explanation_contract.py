#!/usr/bin/env python3
"""B 真实成品、审计六个单因素漏检和两条可复制骨架。"""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from block_layout import check_block_layout, field
from markdown_fences import parse_fences
from local_explanation_contract import prose_content

FIXTURE = ROOT / 'evals/fixtures/local-explanation/ton-state.md'
VALID = FIXTURE.read_text(encoding='utf-8')
SOURCE = (FIXTURE.with_suffix('.st')).read_text(encoding='utf-8')


def remove_column(text, header, column):
    lines = text.splitlines(); active = False; index = None
    for i, line in enumerate(lines):
        if not line.startswith('|'):
            active = False
        elif header in line:
            active = True
            index = [c.strip() for c in line.strip('|').split('|')].index(column)
        if active:
            cells = line.strip('|').split('|'); del cells[index]
            lines[i] = '|' + '|'.join(cells) + '|'
    return '\n'.join(lines) + '\n'


def filled_skeleton(path):
    """填实实际骨架而非拿另一份成品冒充：按字段/表格用途填相同输入。"""
    text = path.read_text(encoding='utf-8')
    if '【输出格式】' in text:
        text = text.split('【输出格式】', 1)[1].split('【代码】', 1)[0]
        text = text[text.index('# <对象与范围>'):]
    else:
        text = next(b['text'] for b in parse_fences(text) if b['lang'] == 'markdown')
    # 按实际字段填同一份 TON 教学事实；不生成任何缺失字段或表头。
    fixture_tables = {}
    from local_explanation_contract import tables
    for header, rows in tables(VALID):
        fixture_tables[header[0]] = rows
    active = ''; cursor = 0; lines = []
    for line in text.splitlines():
        if line.startswith('|'):
            cells = [c.strip() for c in line.strip('|').split('|')]
            if cells[0] in fixture_tables:
                active = cells[0]; cursor = 0
            elif '<' in line and active:
                row = fixture_tables[active][cursor % len(fixture_tables[active])]
                line = '| ' + ' | '.join(row) + ' |'
                cursor += 1
        elif line.startswith('**') and '：' in line:
            label = line.split('**')[1]
            value = field(prose_content(VALID), label)
            if value:
                line = '**' + label + '**：' + value
        lines.append(line)
    text = '\n'.join(lines).rstrip('`\n \t') + '\n'
    text = re.sub(r'<(?![!/]|a )[^>\n]+>', '教学定时与状态片段', text)
    text = re.sub(r'(?ms)(```st\n).*?(\n```)', lambda m:m[1]+SOURCE[:-1]+m[2], text)
    return text


class LocalContractTests(unittest.TestCase):
    def reject(self, bad, message):
        self.assertNotEqual(bad, VALID)
        errors = check_block_layout(bad)
        self.assertTrue(errors, '实际检查器放行坏例：'+message)
        self.assertIn(message, '\n'.join(errors))

    def test_complete_original_source_fixture_passes(self):
        self.assertEqual(check_block_layout(VALID), [])

    def test_missing_variable_type_column_rejected(self):
        self.reject(remove_column(VALID, '| 变量 |', '数据类型'), '数据类型')

    def test_missing_condition_evidence_column_rejected(self):
        self.reject(remove_column(VALID, '| 进入条件 |', '依据'), '依据')

    def test_only_two_real_execution_rows_rejected(self):
        rows = re.findall(r'(?m)^\| [AB] 第[^\n]+\n', VALID)
        bad = VALID
        for row in rows[2:]:
            bad = bad.replace(row, '')
        self.reject(bad, '3')

    def test_execution_count_deduplicates_track_ordinals_and_accepts_time_labels(self):
        duplicate = re.sub(r'(?m)^\| A 第\d+次 ', '| A 第1次 ', VALID)
        self.reject(duplicate, '3')
        times = re.sub(r'(?m)^\| ([AB]) 第\d+次 t=(\d+ms)', r'| \1 \2', VALID)
        self.assertEqual(check_block_layout(times), [])

    def test_execution_ordinals_normalize_chinese_and_group_adjacent_track_names(self):
        from local_explanation_contract import execution_count
        table='| 阶段/执行 | 输入与原状态 | 本段处理 | 执行结果 |\n|---|---|---|---|\n'
        def example(labels):
            return table+'\n'.join('| '+label+' | 前值 | 处理 | 结果 |' for label in labels)
        self.assertEqual(execution_count(example(('第1次','第一次','第 2 次'))),2)
        self.assertEqual(execution_count(example(('A第1次','A第2次','B第3次'))),1)
        self.assertEqual(execution_count(example(('轨迹A第1次','轨迹A第2次','轨迹B第3次'))),1)
        self.assertEqual(execution_count(example(('A 第一次','A 第二次','A 第三次','B第1次','B第2次','B第3次'))),3)
        self.assertEqual(execution_count(example(('0ms','100ms','200ms'))),3)
        self.assertEqual(execution_count(example(('0ms','0ms','100ms'))),2)

    def test_missing_handoff_rejected(self):
        self.reject(re.sub(r'(?m)^\*\*交接要点\*\*：.*\n', '', VALID), '交接要点')

    def test_duplicate_nonempty_process_rejected(self):
        self.reject(VALID.replace('**关键逻辑**：', '**处理过程**：同样的调用和分支也不能重复登记。\n\n**关键逻辑**：'), '处理过程')

    def test_missing_terminal_rejected(self):
        self.reject(VALID.replace('<!-- 本段已完 -->', ''), '结束')

    def test_every_required_field_exactly_once(self):
        for label in ('功能定位','代码职责','设计依据','处理过程','关键逻辑','写法好处','状态变化','场景设定','初始状态','理解要点','交接要点'):
            bad = VALID.replace(f'**{label}**：', f'**{label}**：重复内容不能算作唯一字段。\n\n**{label}**：', 1)
            with self.subTest(label=label): self.reject(bad, label)

    def test_empty_table_cells_are_rejected(self):
        self.reject(VALID.replace('| BOOL；题设声明 | 读 |', '|  | 读 |', 1), '单元格')

    def test_wrong_or_duplicate_terminal_rejected(self):
        for marker in ('<!-- 本段已完 -->\n多余正文', '<!-- 本段已完 -->\n<!-- 继续点：M02 后段 -->', '<!-- 继续点：Mxx 名称 -->'):
            with self.subTest(marker=marker):self.reject(VALID.replace('<!-- 本段已完 -->',marker), '结束')

    def test_fence_payload_cannot_supply_prose_fields_tables_or_terminal(self):
        for label in ('处理过程','交接要点'):
            bad = re.sub(rf'(?m)^\*\*{label}\*\*：.*\n', '', VALID)
            bad = bad.replace('```st\n', f'```st\n// **{label}**：源码里的标签不能算正文\n')
            with self.subTest(label=label): self.reject(bad,label)
        self.reject(VALID.replace('<!-- 本段已完 -->','').replace('```st\n','```st\n// <!-- 本段已完 -->\n'), '结束')

    def test_existing_label_and_h1_boundary_rejections_remain(self):
        self.reject(VALID.replace('**初始状态**','**初始状态与假设**'),'初始状态')
        self.reject('我先解释一下。\n'+VALID,'正式稿')

    def test_both_real_skeletons_filled_pass_actual_checker(self):
        for name in ('local-code-explanation.md','one-page-prompt.md'):
            with self.subTest(name=name):
                self.assertEqual(check_block_layout(filled_skeleton(ROOT/'references'/name)), [])


if __name__ == '__main__': unittest.main(verbosity=2)
