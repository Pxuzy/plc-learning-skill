#!/usr/bin/env python3
"""关键变量必须给数据类型，且不得按变量名前缀猜类型。"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class KeyVarTypesTests(unittest.TestCase):
    def setUp(self):
        self.guide = (ROOT / 'references/handbook-guide.md').read_text()
        self.entry = (ROOT / 'SKILL.md').read_text()

    def test_type_column_required(self):
        self.assertIn('「数据类型」列', self.guide)
        self.assertIn('变量 | 数据类型 | 方向 | 含义 | 谁写谁读 | 证据等级', self.guide)

    def test_arrays_and_structs_must_be_expanded(self):
        self.assertIn('下标范围与元素类型', self.guide)
        self.assertIn('成员路径', self.guide)

    def test_prefix_guessing_forbidden(self):
        self.assertIn('不得按变量名前缀猜类型', self.guide)

    def test_naming_inference_supports_understanding_without_confirming_declarations(self):
        style = (ROOT / 'references/inline-comment-style.md').read_text()
        for clue in ('`g_`', '`a`', '`x`', '`ax` / `ast`', '`To` / `From`'):
            self.assertIn(clue, style)
        for evidence in ('英文词段', '作者注释', '实际读写', '明确标为推断'):
            self.assertIn(evidence, style)
        self.assertIn('g_axLampPermit', style)
        self.assertIn('只有声明可见后才能', style)
        self.assertIn('不能把第一个字母机械地都当作前缀', style)
        self.assertIn('含义列', style)
        self.assertIn('类型列仍写“未知”', style)
        self.assertIn('允许结合前缀', self.entry)
        self.assertIn('不得当作已确认的类型、作用域、接口方向或物理动作', self.entry)

    def test_type_effects_must_be_stated(self):
        self.assertIn('溢出', self.guide)
        self.assertIn('PLC-KEY-VAR-TYPES', self.entry)


if __name__ == '__main__':
    unittest.main(verbosity=2)
