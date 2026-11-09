#!/usr/bin/env python3
"""混排语言必须逐单元清点，再给综合结论；不得整篇贴一个语言标签。"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class UnitLanguageTests(unittest.TestCase):
    def setUp(self):
        self.reading = (ROOT / 'references/code-reading.md').read_text()
        self.guide = (ROOT / 'references/handbook-guide.md').read_text()
        self.entry = (ROOT / 'SKILL.md').read_text()

    def test_unit_inventory_is_defined(self):
        for kw in ('语言单元清点', '清点表', '判定依据', '综合结论'):
            self.assertIn(kw, self.reading)

    def test_mixed_languages_require_inventory_not_single_label(self):
        self.assertIn('混排（见单元清点表）', self.guide)
        self.assertIn('不得用单一语言标签概括整份文档', self.guide)

    def test_entry_forbids_document_level_language_label(self):
        self.assertIn('按**单元**判定', self.entry)
        self.assertIn('代码单元清点表', self.entry)

    def test_seven_cases_are_separated(self):
        for kw in ('调用处与被调体内语言不同', 'LAD 网络里嵌 ST 指令框', 'SFC/STL', '冲突时报冲突'):
            self.assertIn(kw, self.reading)


if __name__ == '__main__':
    unittest.main(verbosity=2)
