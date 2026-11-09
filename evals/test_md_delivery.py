#!/usr/bin/env python3
"""详细讲解必须交付 .md 文件，不能只在对话里贴正文。"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MdDeliveryTests(unittest.TestCase):
    def test_entry_requires_final_md_file(self):
        entry = (ROOT / 'SKILL.md').read_text()
        self.assertIn('PLC-DELIVERY-FORM', entry)
        self.assertIn('最终必须合并成 `.md` 文件', entry)
        self.assertIn('再合并为一个 Markdown 文件', entry)

    def test_guide_requires_chat_segmentation_and_final_md(self):
        guide = (ROOT / 'references/handbook-guide.md').read_text()
        self.assertIn('### 交付形态', guide)
        self.assertIn('最终必须合并为 `.md` 文件', guide)
        self.assertIn('自动分段连续发在聊天里', guide)

    def test_chat_only_is_explicit_exception(self):
        guide = (ROOT / 'references/handbook-guide.md').read_text()
        self.assertIn('只有用户明确要求纯聊天答复', guide)


if __name__ == '__main__':
    unittest.main(verbosity=2)
