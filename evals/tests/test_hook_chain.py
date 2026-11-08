"""Supported host contract stubs; actual installed host is tested separately."""
import json
import os
import unittest
import test_governance as base


@unittest.skipUnless(os.name == 'posix', 'POSIX shell and executable-bit semantics required')
class HostChainTests(base.GitTests):
    # Inherit repository fixture helpers, not the unrelated base test cases.
    __unittest_skip__ = False

    def host(self):
        host = self.base / 'host'
        host.mkdir()
        # Contract-bearing minimal host stub, not proof of installed host behavior.
        gate = host / 'privacy_gate.py'
        gate.write_text('''import os, pathlib, subprocess, sys
# privacy.originalHooksPath / legacy_hook: supported delegation contract
name = sys.argv[1]
r = subprocess.run(['git', 'config', '--get', 'privacy.originalHooksPath'], capture_output=True)
path = pathlib.Path(r.stdout.decode().strip()) / name
if os.environ.get('FIXTURE_HOST_FAIL'):
    sys.exit(23)
if name == 'pre-commit':
    sys.exit(subprocess.run([str(path), *sys.argv[2:]]).returncode)
if name == 'commit-msg':
    sys.exit(subprocess.run([str(path), *sys.argv[2:]]).returncode)
''')
        for name in ('pre-commit', 'commit-msg'):
            path = host / name
            path.write_text('#!/bin/sh\nexec "' + base.sys.executable + '" "' + str(gate) + '" ' + name + ' "$@"\n')
            path.chmod(0o755)
        self.git('config', '--local', 'core.hooksPath', str(host))
        return host

    def test_stub_host_failure_and_delegation(self):
        self.host()
        self.assertEqual(self.setup('install').returncode, 0)
        self.assertEqual(self.setup('doctor').returncode, 0)
        self.stage()
        blocked = self.git('commit', '-qm', base.VALID,
                           env=dict(self.env, FIXTURE_HOST_FAIL='1'))
        self.assertNotEqual(blocked.returncode, 0)
        self.assertNotEqual(self.git('rev-parse', '--verify', 'HEAD').returncode, 0)
        self.assertEqual(self.git('commit', '-qm', base.VALID).returncode, 0)
        self.stage('next\n')
        self.assertNotEqual(self.git('commit', '-qm', 'bad').returncode, 0)

    def test_host_conflicting_delegate_cycle_and_drift(self):
        host = self.host()
        self.git('config', '--local', 'privacy.originalHooksPath', str(host))
        before = (self.repo / '.git/config').read_bytes()
        self.assertNotEqual(self.setup('install').returncode, 0)
        self.assertEqual(before, (self.repo / '.git/config').read_bytes())
        self.git('config', '--local', '--unset', 'privacy.originalHooksPath')
        self.assertEqual(self.setup('install').returncode, 0)
        (host / 'pre-commit').chmod(0o644)
        self.assertNotEqual(self.setup('doctor').returncode, 0)
        (host / 'pre-commit').chmod(0o755)
        (host / 'privacy_gate.py').write_text('# drift\n')
        self.assertNotEqual(self.setup('doctor').returncode, 0)

    def test_host_other_stages_args_stdin_exit_untouched(self):
        host = self.host()
        hook = host / 'pre-push'
        hook.write_text('#!/bin/sh\ncat > payload\nprintf "%s\\n" "$@" > arguments\nexit 27\n')
        hook.chmod(0o755)
        before = hook.read_bytes()
        self.assertEqual(self.setup('install').returncode, 0)
        self.assertEqual(self.git('config', '--get', 'core.hooksPath').stdout.strip(),
                         str(host).encode())
        probe = base.run('git', 'hook', 'run', '--ignore-missing', 'plc-hook-capability-probe',
                         cwd=self.repo, env=self.env)
        hook_args = ('fixture', 'local-target')
        if probe.returncode == 0:
            result = base.run('git', 'hook', 'run', '--to-stdin=/dev/stdin', 'pre-push', '--',
                              *hook_args, data=b'payload fixture\n', cwd=self.repo, env=self.env)
        else:
            # Older Git lacks `git hook run`; execute the unchanged host script directly.
            result = base.run(hook, *hook_args, data=b'payload fixture\n',
                              cwd=self.repo, env=self.env)
        self.assertEqual(result.returncode, 27)
        self.assertEqual((self.repo / 'payload').read_bytes(), b'payload fixture\n')
        self.assertEqual((self.repo / 'arguments').read_text(), 'fixture\nlocal-target\n')
        self.assertEqual(hook.read_bytes(), before)


# Only run host-specific methods here; the base suite is discovered once separately.
for _name in list(base.GitTests.__dict__):
    if _name.startswith('test_'):
        setattr(HostChainTests, _name, None)
