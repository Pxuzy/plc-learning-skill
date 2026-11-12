#!/usr/bin/env python3
"""布局与通俗解释、以及表情覆盖面，必须有可检查的硬规则。"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LayoutPlainTests(unittest.TestCase):
    def setUp(self):
        self.guide = (ROOT / 'references/handbook-guide.md').read_text()
        self.entry = (ROOT / 'SKILL.md').read_text()

    def test_module_numbering_declared_once(self):
        self.assertIn('模块编号方案在文首一次性声明', self.guide)

    def test_modules_are_h3_not_peer_of_chapters(self):
        self.assertIn('模块一律 `###`', self.guide)
        self.assertIn('不得让模块与章同级', self.guide)
        catalog=(ROOT/'references/catalog.md').read_text()
        self.assertIn('单对象模块 H3、小节 H4；多工位工位 H3、模块 H4、小节 H5',catalog)

    def test_each_module_opens_with_plain_sentence(self):
        self.assertIn('一句话说清', self.guide)
        self.assertIn('不含变量名、不含 IF/CASE', self.guide)

    def test_plain_means_conclusion_before_code(self):
        self.assertIn('先讲人话结论，再讲代码依据', self.guide)

    def test_emoji_covers_all_heading_levels(self):
        self.assertIn('章标题、模块标题、模块内小节标题都要带表情', self.entry)
        self.assertIn('PLC-LAYOUT-PLAIN', self.entry)


if __name__ == '__main__':
    unittest.main(verbosity=2)
