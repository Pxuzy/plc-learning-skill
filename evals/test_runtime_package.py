#!/usr/bin/env python3
"""A runtime archive may omit maintenance assets, never runtime ones."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class RuntimePackageTests(unittest.TestCase):
    def test_runtime_scope_rejects_missing_runtime_asset(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp)/'plc-learning-skill'
            dest.mkdir()
            for name in ('SKILL.md','LICENSE'):
                shutil.copy2(ROOT/name,dest/name)
            for directory in ('references','scripts','templates','assets'):
                if (ROOT/directory).is_dir():
                    shutil.copytree(ROOT/directory,dest/directory,ignore=shutil.ignore_patterns('__pycache__'))
            for name in ('git_privacy_gate.py','hooks.py','project_policy.py'):
                (dest/'scripts'/name).unlink()
            cmd=[sys.executable,'-B',str(dest/'scripts/validate_skill.py'),str(dest),'--strict','--runtime']
            good=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(good.returncode,0,good.stdout+good.stderr)
            guide = dest/'references/local-code-explanation.md'
            original = guide.read_text()
            guide.write_text(original + '\n[教学示例](../evals/fixtures/missing-example.md)\n')
            dead = subprocess.run(cmd,capture_output=True,text=True)
            self.assertNotEqual(dead.returncode,0,dead.stdout)
            self.assertIn('missing-example.md',dead.stdout)
            guide.write_text(original)
            for relative in ('templates/code-explanation.md', 'references/local-code-explanation.md'):
                candidate = dest / relative
                saved = candidate.read_text()
                for link in ('[示例](../evals/fixtures/missing-title.md "说明")',
                             '[示例](<../evals/fixtures/missing-angle.md>)',
                             '[示例](../evals/fixtures/missing-plain.md)',
                             '[示例][sample]\n\n[sample]: ../evals/fixtures/missing-reference.md'):
                    with self.subTest(relative=relative, link=link):
                        candidate.write_text(saved + '\n' + link + '\n')
                        dead = subprocess.run(cmd,capture_output=True,text=True)
                        self.assertNotEqual(dead.returncode,0,dead.stdout)
                candidate.write_text(saved)
            guide.unlink()
            bad=subprocess.run(cmd,capture_output=True,text=True)
            self.assertNotEqual(bad.returncode,0)
            self.assertIn('local-code-explanation.md',bad.stdout)

    @staticmethod
    def omitted_assets():
        import ast
        tree = ast.parse((ROOT / 'scripts/validate_skill.py').read_text())
        assignment = next(node for node in tree.body
                          if isinstance(node, ast.Assign) and
                          any(isinstance(t, ast.Name) and t.id == 'MAINTENANCE_ASSETS'
                              for t in node.targets))
        return set(ast.literal_eval(assignment.value))

    def test_distribution_docs_match_exact_maintenance_scope(self):
        import re
        omitted = self.omitted_assets()
        self.assertEqual(len(omitted), 4)
        for relative, marker in (
            ('references/catalog.md', '默认运行包还排除'),
            ('references/skill-maintenance.md', '维护树保留历史兼容与研发资产：'),
        ):
            text = (ROOT / relative).read_text()
            paragraph = next(line for line in text.splitlines() if marker in line)
            self.assertEqual(set(re.findall(
                r'`((?:references|scripts)/[^`]+\.(?:md|py))`',
                paragraph.split('；它们', 1)[0])), omitted)
        catalog = (ROOT / 'references/catalog.md').read_text()
        for relative in omitted:
            row = next(line for line in catalog.splitlines()
                       if line.startswith('| `' + relative + '` |'))
            self.assertIn('仅维护树', row, relative)
        trial = (ROOT / 'references/skill-model-trial.md').read_text()
        self.assertIn('仅指试跑台搭建、模型/工具核对与生成器分层验收', trial)
        self.assertIn('模板校验器反例集仍见', trial)

    def test_trimmed_runtime_keeps_core_and_rejects_reader_dead_links(self):
        omitted = tuple(sorted(self.omitted_assets()))
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / 'plc-learning-skill'
            shutil.copytree(ROOT, dest, ignore=shutil.ignore_patterns(
                '.git', '__pycache__', 'evals', 'docs', '.githooks'))
            for relative in omitted + (
                'scripts/git_privacy_gate.py', 'scripts/hooks.py',
                'scripts/project_policy.py',
            ):
                (dest / relative).unlink()
            cmd = [sys.executable, '-B', str(dest / 'scripts/validate_skill.py'),
                   str(dest), '--strict', '--runtime']
            good = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(good.returncode, 0, good.stdout + good.stderr)
            # Omittable maintenance paths are not a dead-reader-link exemption.
            guide = dest / 'references/local-code-explanation.md'
            original = guide.read_text()
            guide.write_text(original + '\n[历史样例](example-handbook.md)\n')
            bad = subprocess.run(cmd, capture_output=True, text=True)
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn('example-handbook.md', bad.stdout)
            guide.write_text(original)
            (dest / 'references/example-block-handbook.md').unlink()
            bad = subprocess.run(cmd, capture_output=True, text=True)
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn('example-block-handbook.md', bad.stdout)

if __name__=='__main__':
    unittest.main()
