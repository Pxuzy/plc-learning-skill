#!/usr/bin/env python3
"""真实 Markdown 渲染及格式失效反例，不以有一张表代替逐表验收。"""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MarkdownSyntaxTests(unittest.TestCase):
    def run_doc(self, text, strict=False):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'doc.md'
            path.write_text(text, encoding='utf-8')
            args = [sys.executable, '-B', str(ROOT / 'scripts/check_markdown_format.py'), str(path)]
            if strict:
                args += ['--strict', '--json']
            return subprocess.run(args, capture_output=True, text=True)

    def reject(self, text, rule=None):
        result = self.run_doc(text, strict=rule is not None)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        if rule:
            report = json.loads(result.stdout)
            self.assertTrue(any(x['rule'] == rule for x in report['issues']), report)

    def test_orphan_rows_are_not_tables(self):
        self.reject('# 标题\n\n| 甲 | 乙 |\n| 一 | 二 |\n')

    def test_one_valid_table_cannot_hide_a_broken_second_table(self):
        self.reject('# 标题\n\n| 甲 | 乙 |\n|---|---|\n| 一 | 二 |\n\n## 第二表\n\n| 丙 | 丁 |\n| 三 | 四 |\n')

    def test_unclosed_non_plc_fence_is_rejected(self):
        self.reject('# 标题\n\n```text\n图示内容\n')

    def test_quoted_table_and_metadata_are_not_false_positives(self):
        result = self.run_doc('# 标题\n\n> 工程：示例 | 控制器：未知\n> 版本：示例 | 来源：示例\n\n> | 甲 | 乙 |\n> |---|---|\n> | 一 | 二 |\n')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_orphan_rows_without_outer_pipes_are_rejected(self):
        self.reject('# 标题\n\n甲 | 乙\n一 | 二\n')

    def test_malformed_separator_is_rejected(self):
        self.reject('# 标题\n\n| 甲 | 乙 |\n|---|xx|\n| 一 | 二 |\n')

    def test_html_block_cannot_swallow_table(self):
        self.reject('# 标题\n\n<div>\n| 甲 | 乙 |\n|---|---|\n| 一 | 二 |\n</div>\n')

    def test_extra_cells_cannot_be_silently_dropped(self):
        self.reject('# 标题\n\n| 甲 | 乙 |\n|---|---|\n| 一 | 二 | 三 |\n')

    def test_short_rows_cannot_be_silently_padded(self):
        self.reject('# 标题\n\n| 甲 | 乙 |\n|---|---|\n| 一 |\n')

    def test_ordinary_prose_cannot_be_absorbed_as_a_table_row(self):
        self.reject('# 标题\n\n| 甲 | 乙 |\n|---|---|\n| 一 | 二 |\n本来是正文。\n')

    def test_escaped_pipes_and_real_code_blocks_are_valid(self):
        text = '# 标题\n\n| 甲 | 乙 |\n|---|---|\n| `a\\|b` | 值 |\n\n```text\n| 示例 | 不必渲染 |\n| 原始 | 数据 |\n```\n'
        result = self.run_doc(text)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_blank_line_before_heading_is_required_in_strict_mode(self):
        self.reject('# 标题\n\n正文。\n## 子标题\n\n说明。\n', 'heading-spacing')

    def test_unknown_html_placeholder_is_not_visible_text(self):
        self.reject('# 标题\n\n对象为 <POU>。\n', 'hidden-placeholder')

    def test_unresolved_reference_link_is_rejected(self):
        self.reject('# 标题\n\n[示例][missing]\n', 'link-reference')

    def test_anchor_target_is_verified(self):
        self.reject('# 标题\n\n[跳转](#missing)\n', 'link-anchor')

    def test_duplicate_explicit_anchor_is_rejected(self):
        self.reject('# 标题\n\n<a id="same"></a>\n\n说明。\n\n<a id="same"></a>\n', 'duplicate-anchor')

    def test_dependency_failure_does_not_report_success(self):
        code = ('import sys,runpy; sys.path.insert(0,' + repr(str(ROOT / 'scripts')) + '); '
                'sys.argv=' + repr(['check_markdown_format.py', str(ROOT / 'README.md'), '--strict', '--json'])
                + '; runpy.run_path(' + repr(str(ROOT / 'scripts/check_markdown_format.py')) + ',run_name="__main__")')
        result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('markdown-it-py', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
