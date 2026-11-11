#!/usr/bin/env python3
"""模板资产检查真实CLI与破坏性变异；不调用模型。"""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TemplateFormatTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'plc-learning-skill'
        for name in ('references', 'templates', 'scripts', 'assets'):
            if (ROOT / name).is_dir():
                shutil.copytree(ROOT / name, self.root / name,
                                ignore=shutil.ignore_patterns('__pycache__'))

    def run_check(self):
        return subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/validate_template_format.py'),
                               str(self.root), '--json'], capture_output=True, text=True,
                              env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))

    def mutate(self, name, old, new):
        path = self.root / name
        text = path.read_text(encoding='utf-8')
        self.assertIn(old, text)
        changed = text.replace(old, new, 1)
        self.assertNotEqual(text, changed)
        path.write_text(changed, encoding='utf-8')

    def rejected(self, category):
        result = self.run_check()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(any(x['rule'] == category for x in report['errors']), report)

    def test_source_closer_joined_to_code_is_rejected(self):
        self.mutate('templates/code-explanation.md', '\n```\n<!-- source-eof:', '```\n<!-- source-eof:')
        self.rejected('fence')

    def test_templates_are_renderable_without_markdown_wrappers(self):
        sys.path.insert(0, str(ROOT / 'scripts'))
        from markdown_fences import parse_fences
        data = json.loads((ROOT / 'assets/template-format-contracts.json').read_text())
        paths = {e['path'] for e in data['templates']}
        paths.add('references/local-code-explanation.md')
        paths.add('references/code-reading.md')
        for name in sorted(paths):
            with self.subTest(name=name):
                wrappers = [b for b in parse_fences((ROOT / name).read_text())
                            if b['lang'] in {'markdown', 'md'}]
                self.assertFalse(wrappers, f'{name}: headings and tables hidden in code fences')

    def test_wrapping_template_in_markdown_or_plain_fence_is_rejected(self):
        path = self.root / 'templates/project-navigation.md'
        original = path.read_text()
        for language in ('markdown', 'md', 'text', ''):
            with self.subTest(language=language):
                path.write_text('~~~~' + language + '\n' + original + '\n~~~~\n')
                self.rejected('template-render')
        path.write_text(original)

    def test_wrapping_authority_in_markdown_is_rejected(self):
        path = self.root / 'references/local-code-explanation.md'
        path.write_text('~~~~markdown\n' + path.read_text() + '\n~~~~\n')
        self.rejected('template-render')

    def test_all_registered_assets_pass(self):
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['checked'], 12)
        self.assertFalse(report['errors'])

    def test_missing_heading_inside_copyable_fence_is_rejected(self):
        self.mutate('templates/code-explanation.md', '#### 4. 形象示例', '#### 4. 示例改名')
        self.rejected('heading-contract')

    def test_wrong_heading_level_is_rejected(self):
        self.mutate('templates/code-explanation.md', '#### 5. 程序交互与段间交接',
                    '### 5. 程序交互与段间交接')
        self.rejected('heading-contract')

    def test_missing_field_is_rejected(self):
        self.mutate('templates/code-explanation.md', '**处理过程**：', '**过程**：')
        self.rejected('field-contract')

    def test_missing_table_column_is_rejected(self):
        self.mutate('templates/code-explanation.md', '| 变量 | 数据类型 | 方向 | 含义 | 谁写谁读 | 证据等级 |',
                    '| 变量 | 数据类型 | 方向 | 含义 | 证据等级 |')
        self.rejected('table-contract')

    def test_missing_compat_declaration_is_rejected(self):
        path = self.root / 'templates/handbook-index.md'
        text = path.read_text(encoding='utf-8')
        lines = text.splitlines(keepends=True)
        removed = [x for x in lines if 'template-compat:' in x]
        self.assertEqual(len(removed), 1)
        path.write_text(''.join(x for x in lines if x not in removed), encoding='utf-8')
        self.rejected('compat-declaration')

    def test_broken_fence_is_rejected(self):
        self.mutate('templates/code-explanation.md', '```st\n', '````st\n')
        self.rejected('fence')

    def test_empty_section_is_rejected(self):
        self.mutate('references/template-overview.md', '<这套程序控制什么设备、完成什么工艺、主要输出是什么。>', '')
        self.rejected('empty-section')

    def test_new_unregistered_template_is_rejected(self):
        (self.root / 'templates/unregistered.md').write_text(
            '# 新模板\n<!-- template-id: EXTRA@1.0 -->\n', encoding='utf-8')
        self.rejected('unregistered-template')

    def test_missing_asset_is_rejected(self):
        (self.root / 'references/template-state-machine.md').unlink()
        self.rejected('missing-file')

    def test_compatibility_mapping_cannot_silently_drop_authority_columns(self):
        self.mutate('templates/handbook-index.md',
                    '| 册号 | 手册文件 | 对象范围 | 类型 | 段数 | 覆盖状态 | 来源证据 |',
                    '| 册号 | 手册文件 | 对象范围 | 覆盖状态 | 来源证据 |')
        self.rejected('compat-field-map')

    def test_runtime_copy_runs_without_maintenance_assets(self):
        for name in ('git_privacy_gate.py', 'hooks.py', 'project_policy.py'):
            (self.root / 'scripts' / name).unlink()
        result = subprocess.run([sys.executable, '-B',
                                 str(self.root / 'scripts/validate_template_format.py'),
                                 str(self.root), '--json'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['checked'], 12)

    def test_empty_contract_is_rejected(self):
        path = self.root / 'assets/template-format-contracts.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['templates'] = []
        path.write_text(json.dumps(data), encoding='utf-8')
        self.rejected('contract-coverage')

    def test_blank_field_value_is_rejected(self):
        path = self.root / 'templates/code-explanation.md'
        text = path.read_text(encoding='utf-8')
        import re
        text, count = re.subn(r'(?m)^\*\*处理过程\*\*：.*$', '**处理过程**：', text)
        self.assertEqual(count, 1)
        path.write_text(text, encoding='utf-8')
        self.rejected('empty-field')

    def test_heading_suffix_cannot_hide_a_rename(self):
        self.mutate('templates/code-explanation.md', '#### 4. 形象示例', '#### 4. 形象示例已废弃')
        self.rejected('heading-contract')

    def test_table_delimiter_is_required(self):
        self.mutate('templates/code-explanation.md', '|---|---|---|---|---|---|', '|bad|bad|bad|bad|bad|bad|')
        self.rejected('table-structure')

    def test_source_placeholder_fence_is_required(self):
        path = self.root / 'templates/code-explanation.md'
        text = path.read_text(encoding='utf-8')
        import re
        text, count = re.subn(r'(?m)^```st\n.*?^```\n', '', text, flags=re.DOTALL)
        self.assertEqual(count, 1)
        path.write_text(text, encoding='utf-8')
        self.rejected('source-slot')

    def test_bad_contract_type_is_reported_as_json(self):
        path = self.root / 'assets/template-format-contracts.json'
        path.write_text('[]', encoding='utf-8')
        self.rejected('contract-schema')

    def test_commented_header_is_not_a_table(self):
        header = '| 变量 | 数据类型 | 方向 | 含义 | 谁写谁读 | 证据等级 |'
        self.mutate('templates/code-explanation.md', header, '<!--\n'+header+'\n-->')
        self.rejected('table-contract')

    def test_comment_only_section_is_empty(self):
        self.mutate('references/template-overview.md', '<这套程序控制什么设备、完成什么工艺、主要输出是什么。>',
                    '<!--\n只有注释\n-->')
        self.rejected('empty-section')

    def test_compat_authority_cannot_point_to_itself_or_an_example(self):
        for target in ('templates/code-explanation.md', 'references/example-fb.md'):
            with self.subTest(target=target):
                for name in ('references/template-index.md', 'templates/code-explanation.md'):
                    path = self.root / name
                    original = (ROOT / name).read_text(encoding='utf-8')
                    path.write_text(original.replace('references/local-code-explanation.md', target), encoding='utf-8')
                self.rejected('compat-authority')

    def test_contract_cannot_use_empty_heading(self):
        path = self.root / 'assets/template-format-contracts.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['templates'][1]['headings'] = [[1, '']]
        path.write_text(json.dumps(data), encoding='utf-8')
        self.rejected('contract-schema')

    def test_specs_keep_reviewed_minimum_structure(self):
        data = json.loads((ROOT / 'assets/template-format-contracts.json').read_text(encoding='utf-8'))
        self.assertEqual([(len(e['headings']), len(e['tables'])) for e in data['templates']],
                         [(27,16),(8,1),(14,3),(5,2),(5,3),(13,3),(8,3),(11,7),(10,3),(8,4),(10,6),(6,3)])
        # 20 项含骨架里的“控制目标与范围”，契约字段集合须与可复制骨架一致。
        self.assertEqual(len(data['templates'][9]['fields']), 20)

    def test_parent_path_in_contract_is_rejected(self):
        path = self.root / 'assets/template-format-contracts.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['templates'][0]['path'] = '../outside.md'
        path.write_text(json.dumps(data), encoding='utf-8')
        self.rejected('unsafe-path')

    def test_extra_copyable_part_is_rejected(self):
        self.mutate('templates/code-explanation.md', '<!-- 本段已完 -->',
                    '<!-- 本段已完 -->\n\n#### 6. 附录补充说明\n\n补充说明。')
        self.rejected('heading-contract')

    def test_extra_copyable_field_is_rejected(self):
        self.mutate('templates/code-explanation.md', '**验证状态**：<',
                    '**边界条件**：<占位>\n\n**验证状态**：<')
        self.rejected('field-contract')

    def test_extra_authority_field_is_rejected(self):
        self.mutate('references/local-code-explanation.md', '**验证状态**：<',
                    '**边界条件**：<占位>\n\n**验证状态**：<')
        self.rejected('authority-field')

    def test_authority_heading_rename_is_rejected(self):
        self.mutate('references/workflows/project-navigation.md',
                    '## 5. 进入标准讲解', '## 5. 进入讲解')
        self.rejected('authority-heading')

    def test_authority_spec_requires_view_and_headings(self):
        path = self.root / 'assets/template-format-contracts.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['templates'][10]['authority_spec']['view'] = 'sideways'
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        self.rejected('contract-schema')

    def test_extra_authority_section_is_rejected(self):
        self.mutate('references/workflows/project-navigation.md', '## 6. 交付与继续学习',
                    '## 6. 交付与继续学习\n\n## 7. 追加章节')
        self.rejected('authority-heading')

    def test_trailing_symbol_outside_old_emoji_range_is_decorative(self):
        self.mutate('templates/code-explanation.md', '#### 4. 形象示例 🧪',
                    '#### 4. 形象示例 ⭐')
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_source_slot_rule_does_not_bind_version_literal(self):
        for name in ('assets/template-format-contracts.json', 'templates/code-explanation.md',
                     'references/template-index.md'):
            path = self.root / name
            text = path.read_text(encoding='utf-8')
            self.assertIn('CODE@1.0', text)
            path.write_text(text.replace('CODE@1.0', 'CODE@1.1'), encoding='utf-8')
        path = self.root / 'templates/code-explanation.md'
        import re
        text, count = re.subn(r'(?m)^```st\n.*?^```\n', '', path.read_text(encoding='utf-8'), flags=re.DOTALL)
        self.assertEqual(count, 1)
        path.write_text(text, encoding='utf-8')
        self.rejected('source-slot')


    def test_required_field_cannot_be_hidden_in_prose(self):
        self.mutate('templates/code-explanation.md', '**处理过程**：<', '正文提到 **处理过程**：<')
        self.rejected('field-contract')

    def test_required_authority_field_cannot_be_hidden_in_prose(self):
        self.mutate('references/local-code-explanation.md', '**处理过程**：<', '正文提到 **处理过程**：<')
        self.rejected('authority-field')

    def test_body_template_extra_section_is_rejected(self):
        path = self.root / 'templates/project-navigation.md'
        path.write_text(path.read_text() + '\n## 7. 追加章节\n\n新增说明。\n')
        self.rejected('heading-contract')

    def test_extra_table_is_rejected(self):
        self.mutate('templates/code-explanation.md', '<!-- 本段已完 -->',
                    '| 新增A | 新增B |\n|---|---|\n| 值A | 值B |\n\n<!-- 本段已完 -->')
        self.rejected('table-contract')

    def test_authority_table_column_change_is_rejected(self):
        self.mutate('references/local-code-explanation.md',
                    '| 变量 | 数据类型 | 方向 | 含义 | 谁写谁读 | 证据等级 |',
                    '| 变量 | 数据类型 | 方向 | 含义 | 谁写谁读 | 错误列 |')
        self.rejected('authority-table')

    def test_nested_unregistered_template_is_rejected(self):
        path = self.root / 'templates/nested/extra.md'
        path.parent.mkdir()
        path.write_text('# 新模板\n')
        self.rejected('unregistered-template')


if __name__ == '__main__':
    unittest.main(verbosity=2)
