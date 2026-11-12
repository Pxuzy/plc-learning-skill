#!/usr/bin/env python3
"""长文必须自动切分、连续覆盖全部代码并最终合并。"""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LongTextDeliveryTests(unittest.TestCase):
    def test_long_text_contract_selects_automatic_continuous_segmentation(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        for phrase in ("自动分段", "连续完成全部批次", "不等待用户逐段回复", "完整覆盖清单"):
            self.assertIn(phrase, skill)

    def test_long_text_contract_tracks_coverage_and_merges_final_markdown(self):
        workflow = (ROOT / "references/workflow.md").read_text(encoding="utf-8")
        for phrase in ("批首标批次", "批尾记录已完成", "未完成", "合并为一份 Markdown"):
            self.assertIn(phrase, workflow)
        self.assertIn("覆盖清单一一对应", workflow)

    def test_comment_preflight_and_concise_handbook_are_connected(self):
        style = (ROOT / 'references/inline-comment-style.md').read_text()
        entry = (ROOT / 'SKILL.md').read_text()
        guide = (ROOT / 'references/handbook-guide.md').read_text()
        workflow = (ROOT / 'references/workflow.md').read_text()
        template = (ROOT / 'references/template-handbook.md').read_text()
        for phrase in ('每次生成或改写注释前', '变量命名辅助推断', 'inline-comment-examples.md', '上下文压缩'):
            self.assertIn(phrase, style)
        self.assertIn('注释前置参考', entry)
        self.assertIn('简洁写作提示词', guide)
        self.assertIn('章与模块两级目录', workflow)
        self.assertIn('风格参考摘要', workflow)
        self.assertIn('关键变量前置：每个逻辑单元', template)

    def test_long_document_behavior_case_catches_premature_stopping(self):
        cases = (ROOT / "evals/cases.md").read_text(encoding="utf-8")
        section = cases[cases.index("## Case 14：长文档分批") : cases.index("## Case 15：")]
        for phrase in ("未完成全部范围", "每批结束就等待用户回复"):
            self.assertIn(phrase, section)


if __name__ == "__main__":
    unittest.main(verbosity=2)
