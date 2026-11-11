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

if __name__=='__main__':
    unittest.main()
