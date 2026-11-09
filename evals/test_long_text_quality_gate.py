#!/usr/bin/env python3
"""Long-text acceptance must test teaching quality, not only coverage."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LongTextQualityGateTests(unittest.TestCase):
    def test_long_text_entry_routes_to_semantic_quality_gate(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("长文逐段质量验收", skill)
        self.assertIn("覆盖与讲解质量分开计数", skill)

    def test_long_text_workflow_requires_segment_level_semantic_acceptance(self):
        workflow = (ROOT / "references/workflow.md").read_text(encoding="utf-8")
        segment_rules = workflow.split("### 长文本分段输出", 1)[1].split("### 对象讲解硬约束", 1)[0]
        for phrase in (
            "逐段质量验收",
            "条件真假路径",
            "具体初值",
            "至少三次连续执行",
            "只改变一个因素",
            "讲解质量未通过",
            "不得标记为已讲解",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, segment_rules)

    def test_long_text_behavior_case_rejects_coverage_only_outputs(self):
        cases = (ROOT / "evals/cases.md").read_text(encoding="utf-8")
        section = cases.split("## Case 14：长文档分批", 1)[1].split("## Case 15：", 1)[0]
        for phrase in (
            "逐段的因果讲解",
            "条件真假路径",
            "三次连续执行",
            "单因素删改反例",
            "只清点并原样贴回源码不算讲解",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, section)

    def test_behavior_microtest_separates_delivery_from_teaching_quality(self):
        workflow = (ROOT / "references/workflow.md").read_text(encoding="utf-8")
        section = workflow.split("### 行为微测的验收口径", 1)[1].split("### 测试夹具与真实归档的可行性预审", 1)[0]
        for phrase in (
            "完成数量",
            "逐段质量通过数量",
            "覆盖率不能代替讲解质量",
            "有一段未通过就不能报告整体讲解通过",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, section)


if __name__ == "__main__":
    unittest.main(verbosity=2)