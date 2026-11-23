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

    def test_smc2_route_defaults_to_a_full_markdown_export(self):
        entry = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
        workflow = (ROOT / 'references/omron-smc2-xml-workflow.md').read_text(encoding='utf-8')
        route = next(line for line in entry.splitlines() if line.startswith('| 已确认 Omron NJ/NX Sysmac Studio SMC2 |'))
        self.assertIn('--output-md', route)
        self.assertIn('默认', route)
        self.assertIn('python3 -B "<技能绝对目录>/scripts/smc2_locate_pou.py"', workflow)
        self.assertIn('python3 -B -m scripts.smc2_locate_pou', workflow)
        self.assertIn('不依赖 `PYTHONPATH`', workflow)
        self.assertIn('--include-source', workflow)
        self.assertIn('兼容', workflow)

    def test_exported_source_is_a_draft_that_continues_the_original_task(self):
        archive = (ROOT / 'references/source-archive.md').read_text(encoding='utf-8')
        self.assertIn('导出底稿', archive)
        self.assertIn('导出后继续原任务', archive)
        self.assertIn('完成导出不等于后续任务已完成', archive)
        self.assertIn('讲解、分析或修改请求', archive)

    def test_delivery_uses_host_supported_attachments_and_downloads(self):
        runtime = (ROOT / 'references/runtime-guidance.md').read_text(encoding='utf-8')
        form = runtime.split('PLC-DELIVERY-FORM', 1)[1].split('\n- **PLC-', 1)[0]
        self.assertIn('宿主实际支持的附件或下载方式', form)
        self.assertIn('遵守宿主更高优先级限制', form)
        self.assertIn('内部文件位置用于模型续读', form)
        self.assertNotIn('MEDIA:', form)
        self.assertNotIn('/mnt/', form)
        self.assertNotIn('固定输出根', form)

    def test_catalog_records_export_and_test_coverage_without_new_asset_rows(self):
        catalog = (ROOT / 'references/catalog.md').read_text(encoding='utf-8')
        locator = next(line for line in catalog.splitlines() if line.startswith('| `scripts/smc2_locate_pou.py` |'))
        locate_test = next(line for line in catalog.splitlines() if line.startswith('| `evals/test_smc2_locate_pou.py` |'))
        delivery_test = next(line for line in catalog.splitlines() if line.startswith('| `evals/test_md_delivery.py` |'))
        self.assertIn('Markdown', locator)
        self.assertIn('Markdown', locate_test)
        self.assertIn('SMC2', delivery_test)


    def test_source_export_readability_and_followup_checks_remain_required(self):
        source = (ROOT / 'references/source-archive.md').read_text(encoding='utf-8')
        validation = (ROOT / 'references/output-validation.md').read_text(encoding='utf-8')
        self.assertIn('中文变量表', source)
        self.assertIn('原始声明', source)
        self.assertIn('源码逐字符', validation)
        self.assertIn('变量表', validation)
        self.assertIn('导出校验不能代替后续讲解', validation)
        for relative in ('SKILL.md', 'references/runtime-guidance.md'):
            text = (ROOT / relative).read_text(encoding='utf-8')
            self.assertNotIn('MEDIA:/绝对路径', text)
            self.assertNotIn('并回报绝对路径', text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
