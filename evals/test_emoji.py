#!/usr/bin/env python3
"""表情是阅读路标：标题必须带，不能整篇素面朝天。"""
import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
EMOJI = re.compile('[\U0001F300-\U0001FAFF\u2600-\u27BF]')


class EmojiRuleTests(unittest.TestCase):
    def test_rule_requires_title_emoji(self):
        guide = (ROOT / 'references/handbook-guide.md').read_text()
        self.assertIn('每个模块标题必须带一个表情', guide)
        self.assertIn('整篇没有表情按版式缺陷处理', guide)

    def test_rule_no_longer_says_optional(self):
        guide = (ROOT / 'references/handbook-guide.md').read_text()
        self.assertNotIn('不要求每章都有', guide)
        self.assertNotIn('版式检查不要求标题加表情', guide)

    def test_entry_states_mandatory_title_emoji(self):
        entry = (ROOT / 'SKILL.md').read_text()
        self.assertIn('每个模块标题必须带表情', entry)
        self.assertNotIn('表情只进标题', entry)

    def test_template_carries_emoji_examples(self):
        tpl = (ROOT / 'references/template-handbook.md').read_text()
        self.assertGreaterEqual(len(set(EMOJI.findall(tpl))), 6)


if __name__ == '__main__':
    unittest.main(verbosity=2)
