#!/usr/bin/env python3
"""Effective hook checks must work without owning shared-worktree config."""
from pathlib import Path
import importlib.util
import unittest
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('hooks',ROOT/'scripts/hooks.py')
assert spec is not None and spec.loader is not None
hooks=importlib.util.module_from_spec(spec)
spec.loader.exec_module(hooks)

class EffectiveChainTests(unittest.TestCase):
    def test_effective_doctor_is_available(self):
        self.assertTrue(callable(getattr(hooks,'diagnose_effective',None)),
                        'effective chain inspection must not require installer state')

    def test_effective_doctor_accepts_exact_delegate_and_rejects_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'candidate'
            host=Path(temp)/'host'
            delegate=Path(temp)/'delegate'
            for directory in (root/'.githooks',host,delegate):
                directory.mkdir(parents=True)
                for name in (*hooks.REQUIRED,'python.sh'):
                    target=directory/name
                    target.write_text('exact hook bytes')
                    target.chmod(0o755)
            def effective(*args,**kwargs):
                return str(host if args[-1]=='core.hooksPath' else delegate)
            with patch.object(hooks,'ROOT',root),patch.object(hooks,'dependencies'),patch.object(hooks,'host_contract'),patch.object(hooks,'git',side_effect=effective):
                hooks.diagnose_effective()
                (delegate/'pre-commit').write_text('different hook bytes')
                with self.assertRaisesRegex(hooks.SetupError,'differs'):
                    hooks.diagnose_effective()

if __name__=='__main__':
    unittest.main()
