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
            (dest/'references/local-code-explanation.md').unlink()
            bad=subprocess.run(cmd,capture_output=True,text=True)
            self.assertNotEqual(bad.returncode,0)
            self.assertIn('local-code-explanation.md',bad.stdout)

if __name__=='__main__':
    unittest.main()
