#!/usr/bin/env python3
"""Confirmed default: short business AI notes on every code/structure line."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'evals'))
from test_local_explanation_contract import VALID, SOURCE

CODE = ('IF xPreviewEnabled THEN // AI: 检查面板预览是否获准\n'
        '    xPanelPreview := TRUE; // AI: 标记面板预览开启\n'
        'END_IF; // AI: 面板预览处理结束\n')


class DefaultAnnotations(unittest.TestCase):
    def cli(self, script, raw, *args, source=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'doc.md'
            path.write_text(raw)
            cmd = [sys.executable, '-B', str(ROOT / 'scripts' / script), str(path), *args]
            if source is not None:
                src = Path(directory) / 'source.st'
                src.write_text(source)
                cmd += ['--source', str(src)]
            return subprocess.run(cmd, capture_output=True, text=True)

    def test_entry_routes_to_all_eleven_confirmed_rules(self):
        import re
        entry = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
        contract = (ROOT / 'references/core-requirements.md').read_text(encoding='utf-8')
        self.assertIn('references/core-requirements.md', entry)
        ids = re.findall(r'^\| (R\d+) \|', contract.split('## 与检查器的对应', 1)[0], re.M)
        self.assertEqual(ids, [f'R{i}' for i in range(1, 12)])
        self.assertIn('结构闭合行均覆盖', contract)
        self.assertNotIn('默认模式只对**有信息量的行**', entry)

    def test_runtime_examples_follow_default_annotation_contract(self):
        sys.path.insert(0, str(ROOT / 'scripts'))
        from check_plc_comments import check_default_annotations
        for name in ('example-block-handbook.md', 'example-handbook.md'):
            raw = (ROOT / 'references' / name).read_text(encoding='utf-8')
            self.assertEqual(check_default_annotations(raw), [], name)
        forbidden = ('B 默认不追加注释', '纯闭合行可豁免', '纯闭合行可合并',
                     '仅纯闭合行可登记省略理由', '纯闭合可合并')
        for name in ('code-reading.md', 'template-interface-instances.md',
                     'template-state-machine.md', 'template-index.md', 'teaching-from-scratch.md'):
            raw = (ROOT / 'references' / name).read_text(encoding='utf-8')
            for phrase in forbidden:
                self.assertNotIn(phrase, raw, name)

    def test_default_comment_cli_rejects_each_removed_note(self):
        good = '```st\n' + CODE + '```\n'
        result = self.cli('check_plc_comments.py', good)
        self.assertEqual(result.returncode, 0, result.stdout)
        for note in (' // AI: 检查面板预览是否获准', ' // AI: 标记面板预览开启', ' // AI: 面板预览处理结束'):
            result = self.cli('check_plc_comments.py', good.replace(note, ''))
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn('逐行', result.stdout)

    def test_blank_and_comment_only_lines_need_no_extra_notes(self):
        raw = '```st\n// 原说明\n(* 原有多行\n   注释 *)\n\n' + CODE + '```\n'
        result = self.cli('check_plc_comments.py', raw)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_existing_author_note_is_preserved_but_new_note_is_required(self):
        result = self.cli('check_plc_comments.py', '```st\nxPanelPreview := TRUE; // 原作者：显示面板预览\n```\n')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('逐行', result.stdout)

    def test_source_mode_is_explicit_and_cannot_be_mixed_with_generation(self):
        raw = '```st\nIF xPreviewEnabled THEN\nxPanelPreview := TRUE;\nEND_IF;\n```\n'
        result = self.cli('check_plc_comments.py', raw, '--original-source')
        self.assertEqual(result.returncode, 0, result.stdout)
        result = self.cli('check_plc_comments.py', raw, '--original-source', '--require-every-line')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_legacy_mode_cannot_override_explicit_every_line(self):
        result = self.cli('check_plc_comments.py', '```st\n' + CODE + '```\n',
                          '--legacy-selective', '--require-every-line')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_local_modes_cannot_be_combined(self):
        result = self.cli('check_local_explanation.py', VALID, '--original-source',
                          '--allow-ai-tails', source=SOURCE)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_local_default_refuses_unannotated_document(self):
        result = self.cli('check_local_explanation.py', VALID, source=SOURCE)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('逐行', result.stdout)
        result = self.cli('check_local_explanation.py', VALID, '--original-source', source=SOURCE)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_local_default_accepts_append_only_notes_without_extra_flag(self):
        notes = ['请求与许可同时成立时累计稳定等待时间', '先检查故障路径是否被选中', '故障路径撤销运行标志',
                 '前述故障路径未选中时再检查计时到期与许可', '计时到期且许可成立时置位运行标志',
                 '结束本次运行状态选路', '由许可与无故障状态生成就绪标志']
        annotated = ''.join(line.rstrip('\n') + ' // AI: ' + note + '\n'
                            for line, note in zip(SOURCE.splitlines(keepends=True), notes))
        doc = VALID.replace(SOURCE, annotated)
        result = self.cli('check_local_explanation.py', doc, source=SOURCE)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_handbook_default_reports_unannotated_closure(self):
        result = self.cli('validate_handbook.py', '# 教学 📘\n\n```st\n' + CODE.replace(' // AI: 面板预览处理结束', '') + '```\n')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('逐行', result.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
