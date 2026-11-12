#!/usr/bin/env python3
"""生成契约在降级提示、正例和执行步骤中一致；不证明模型语义。"""
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from check_plc_comments import check_default_annotations

class GenerationContract(unittest.TestCase):
    def test_fallback_embeds_complete_line_coverage(self):
        text = (ROOT / 'references/one-page-prompt.md').read_text()
        prompt = text.split('````', 2)[1]
        for phrase in ('每条非空', '条件续行', '结构闭合行', ' // AI: '):
            self.assertIn(phrase, prompt)
        self.assertNotIn('代码围栏与输入逐字符一致', text)
        self.assertIn('剥离本轮新增尾注后', text)

    def test_positive_quality_examples_obey_default(self):
        text = (ROOT / 'references/comment-quality.md').read_text()
        self.assertEqual(check_default_annotations(text), [])

    def test_fallback_requires_actual_execution_and_recheck(self):
        text = (ROOT / 'references/one-page-prompt.md').read_text().split('````', 2)[1]
        for phrase in ('check_local_explanation.py', 'check_plc_comments.py', 'check_markdown_format.py', '--source', '重新运行', '未执行'):
            self.assertIn(phrase, text)
        self.assertIn('**批判性审查**', text)
        self.assertIn('**验证状态**', text)

    def test_entry_routes_validation_and_limits_loading(self):
        text = (ROOT / 'SKILL.md').read_text()
        self.assertLess(len(text.encode()), 24000, '运行入口仍被细则与维护材料淹没')
        self.assertIn('references/output-validation.md', text)
        self.assertIn('scripts/check_local_explanation.py', text)
        self.assertIn('重新运行', text)
        self.assertIn('未校验草稿', text)

    def test_entry_has_actionable_delivery_checklist(self):
        text = (ROOT / 'SKILL.md').read_text()
        verification = text.split('## 交付门槛（Verification）', 1)[1].split('### 维护入口', 1)[0]
        for item in ('源码保真', '应注行覆盖', '五部分及字段', 'Markdown 渲染', '语义审查'):
            self.assertTrue(any(line.startswith('- [ ] ') and item in line for line in verification.splitlines()), item)

    def test_entry_rules_are_scannable_without_losing_contracts(self):
        text = (ROOT / 'SKILL.md').read_text()
        for line in text.splitlines():
            if line.startswith('- **PLC-'):
                self.assertLessEqual(len(line), 350, '一条规则混入过多次级要求，应拆成可扫描的子项')
        for heading in ('### 源码、注释与证据', '### 教学结构与连续覆盖', '### 执行语义与边界', '### 交付与用户指定规则'):
            self.assertIn(heading, text)

    def test_reviewed_entry_preserves_summary_and_limits_exemptions(self):
        text = (ROOT / 'SKILL.md').read_text()
        opening = text.split('## 读者与成功标准', 1)[0]
        self.assertIn('从整体到局部', opening)
        self.assertIn('功能定位', opening)
        segment = text.split('- **PLC-SEGMENT-DELIVERY**', 1)[1].split('- **PLC-TITLE-EMOJI**', 1)[0]
        self.assertIn('先建完整覆盖清单', segment)
        self.assertIn('自动续接', segment)
        self.assertIn('仅当模式或语言明确不适用时', text)
        self.assertIn('不得以不适用为由跳过本任务必需项', text)

if __name__ == '__main__':
    unittest.main(verbosity=2)
