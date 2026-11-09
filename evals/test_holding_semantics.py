#!/usr/bin/env python3
"""保持/复位反例不得教错：条件失效只跳过写入，不等于关闭输出。"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class HoldingSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.guide = (ROOT / 'references/handbook-guide.md').read_text()

    def test_latch_pattern_is_not_taught_as_closing_on_input_flicker(self):
        self.assertNotIn('错误做法：IF xPartRequest THEN yValve := TRUE; END_IF;', self.guide)

    def test_following_assignment_is_a_comparison_not_unconditionally_wrong(self):
        self.assertIn('改版：xClampRequest := xRequest;', self.guide)
        self.assertIn('若需求是跟随当前请求，改版可能适用', self.guide)

    def test_missing_clear_source_stays_unknown(self):
        self.assertIn('实际清除点未知', self.guide)
        self.assertNotIn('必须另有复位路径把它清回 FALSE', self.guide)


if __name__ == '__main__':
    unittest.main(verbosity=2)
