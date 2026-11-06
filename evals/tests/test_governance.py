"""Behavioral maintenance tests. All negative data is assembled at runtime."""
from pathlib import Path
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / 'scripts/project_policy.py'
SETUP = ROOT / 'scripts/hooks.py'
PUBLIC = 'fixture@' + 'example.com'
VALID = 'docs(repo): 准备文档\n\n- 添加说明\n'


def run(*args, cwd=None, data=None, env=None):
    return subprocess.run(list(map(str, args)), cwd=cwd, input=data, capture_output=True,
                          env=env, timeout=60)


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(POLICY.is_file(), 'portable project policy must exist')
        spec = importlib.util.spec_from_file_location('project_policy', POLICY)
        self.p = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.p)

    def test_all_types_and_subject_boundary(self):
        for kind in ('feat', 'fix', 'docs', 'refactor', 'chore', 'merge', 'perf',
                     'release', 'revert', 'test', 'build', 'ci', 'style'):
            with self.subTest(kind=kind):
                self.assertEqual(self.p.message_errors(VALID.replace('docs(', kind + '(')), [])
        prefix = 'feat(core): '
        subject = prefix + '中' * (100 - len(prefix))
        self.assertFalse(self.p.message_errors(subject + '\n\n- 内容\n'))
        self.assertTrue(self.p.message_errors(subject + '文\n\n- 内容\n'))

    def test_invalid_formats(self):
        for value in ('', ' ', VALID.replace('docs', 'unknown', 1),
                      VALID.replace('(repo)', '(Repo)'), VALID.replace('(repo)', '(repo1)'),
                      VALID.replace('准备文档', 'English'), VALID.replace('\n\n', '\n'),
                      VALID.replace('- 添加说明', '添加说明'), VALID.replace('- 添加说明', '- '),
                      '\n' + VALID):
            with self.subTest(case=len(value)):
                self.assertTrue(self.p.message_errors(value))

    def test_content_categories_and_redaction_inputs(self):
        bad = [
            ('token', 'gh' + 'p_' + 'A' * 36),
            ('token', 's' + 'k-' + 'a' * 30),
            ('credential', 'pass' + 'word = "' + 'fixture-secret-9182' + '"'),
            ('private-key', '-----BEGIN ' + 'RSA PRIVATE KEY-----'),
            ('email', 'fixture-person@' + 'private-mail.invalid'),
            ('ip', '.'.join(('10', '47', '83', '21'))),
            ('ip', ':'.join(('2001', '4860', '4860', '', '8888'))),
            ('user-path', '/' + 'home' + '/fixture-person/work'),
            ('user-path', 'C:' + '\\Users\\' + 'fixture-person\\work'),
        ]
        for category, value in bad:
            with self.subTest(category=category):
                self.assertIn(category, self.p.content_errors(value.encode()))
        clean = '普通代码 x := 1; docs https://example.com ' + PUBLIC
        clean += ' 12345+fixture@users.noreply.github.com 192.0.2.10 2001:db8::1'
        self.assertFalse(self.p.content_errors(clean.encode()))
        self.assertFalse(self.p.content_errors(('pass' + 'word = "' + '${PASSWORD}' + '"').encode()))
        self.assertTrue(self.p.content_errors(b'\x00\xffbinary'))
        self.assertTrue(self.p.content_errors(b'\xff'))

    def test_material_paths(self):
        for name in ('.env', 'auth/credentials.json', 'keys/id_ed25519', 'cert.p12',
                     'node_modules/a.js', 'build/log', 'private/photo.jpg', 'photo.png',
                     'archive.zip', 'notes.session', '__pycache__/a.pyc', '.env.production',
                     '.env.local', '.DS_Store', '.pytest_cache/state', 'signing.asc'):
            self.assertTrue(self.p.path_errors(name), name)
        for name in ('docs/requirements.md', 'evals/tests/test_governance.py', '.env.example'):
            self.assertFalse(self.p.path_errors(name), name)


class GitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='plc-test-')
        self.base = Path(self.temp.name)
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(('GIT_', 'PLC_'))}
        self.env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1',
                        GIT_AUTHOR_NAME='Public Fixture', GIT_COMMITTER_NAME='Public Fixture',
                        GIT_AUTHOR_EMAIL=PUBLIC, GIT_COMMITTER_EMAIL=PUBLIC,
                        PYTHONDONTWRITEBYTECODE='1')
        self.git('init', '-q')
        for part in ('scripts', '.githooks'):
            if (ROOT / part).exists():
                shutil.copytree(ROOT / part, self.repo / part)

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args, env=None):
        return run('git', *args, cwd=self.repo, env=env or self.env)

    def policy(self, *args, env=None):
        return run(sys.executable, '-B', POLICY, *args, cwd=self.repo, env=env or self.env)

    def setup(self, *args, env=None):
        return run(sys.executable, '-B', self.repo / 'scripts/hooks.py', *args,
                   cwd=self.repo, env=env or self.env)

    def stage(self, text='safe text\n', name='sample.md'):
        target = self.repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        self.assertEqual(self.git('add', '--', name).returncode, 0)
        return target

    def install(self):
        result = self.setup('install', '--local-only')
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_staged_blob_and_preservation(self):
        sensitive = 'gh' + 'p_' + 'Q' * 36
        file = self.stage(sensitive)
        file.write_text('safe worktree\n')
        before = (self.repo / '.git/index').read_bytes(), file.read_bytes()
        result = self.policy('staged')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(sensitive.encode(), result.stdout + result.stderr)
        self.assertEqual(before, ((self.repo / '.git/index').read_bytes(), file.read_bytes()))
        self.stage()
        file.write_text(sensitive)
        self.assertEqual(self.policy('staged').returncode, 0)

    def test_sensitive_paths_deletion_and_symlink(self):
        name = 'gh' + 'p_' + 'R' * 36 + '.md'
        self.stage(name=name)
        result = self.policy('staged')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(name.encode(), result.stdout + result.stderr)
        self.git('rm', '--cached', '--', name)
        (self.repo / 'link').symlink_to('sample.md')
        self.git('add', 'link')
        self.assertNotEqual(self.policy('staged').returncode, 0)

    def test_message_input_and_metadata(self):
        self.stage()
        msg = self.base / 'message'
        for value in (b'', b'\xff', b'bad', VALID.encode()):
            msg.write_bytes(value)
            self.assertEqual(self.policy('message', msg).returncode == 0, value == VALID.encode())
        self.assertNotEqual(self.policy('message', self.base / 'absent').returncode, 0)
        badenv = dict(self.env, GIT_COMMITTER_EMAIL='fixture@' + 'private.invalid')
        result = self.policy('staged', env=badenv)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(badenv['GIT_COMMITTER_EMAIL'].encode(), result.stderr)
        msg.write_text(VALID + '- ' + 'gh' + 'p_' + 'Z' * 36)
        self.assertNotEqual(self.policy('message', msg).returncode, 0)

    def test_scanner_errors_block(self):
        self.assertNotEqual(self.policy('staged', env=dict(self.env, PATH='')).returncode, 0)
        result = run('/usr/bin/python3', '-B', POLICY, 'staged', cwd=self.base, env=self.env)
        self.assertNotEqual(result.returncode, 0)

    def test_install_idempotence_doctor_restore(self):
        before = (self.repo / '.git/config').read_bytes()
        self.install()
        installed = (self.repo / '.git/config').read_bytes()
        self.assertEqual(self.setup('install', '--local-only').returncode, 0)
        self.assertEqual(installed, (self.repo / '.git/config').read_bytes())
        self.assertEqual(self.setup('doctor').returncode, 0)
        self.assertEqual(self.setup('restore').returncode, 0)
        self.assertEqual(self.git('config', '--local', '--get', 'core.hooksPath').returncode, 1)
        self.assertEqual(self.git('config', '--local', '--get', 'user.name').returncode, 1)
        self.assertIn(b'repositoryformatversion', before)

    def test_doctor_missing_dependency_permission_config_and_target(self):
        self.install()
        hook = self.repo / '.githooks/pre-commit'
        hook.chmod(0o644)
        self.assertNotEqual(self.setup('doctor').returncode, 0)
        hook.chmod(0o755)
        self.assertNotEqual(self.setup('doctor', env=dict(self.env, PATH='')).returncode, 0)
        self.git('config', '--local', 'core.hooksPath', '.githooks-missing')
        before = (self.repo / '.git/config').read_bytes()
        self.assertNotEqual(self.setup('doctor').returncode, 0)
        self.assertEqual(before, (self.repo / '.git/config').read_bytes())
        self.assertNotEqual(self.setup('restore').returncode, 0)
        self.git('config', '--local', 'core.hooksPath', str(self.repo / '.githooks'))
        hook.unlink()
        self.assertNotEqual(self.setup('doctor').returncode, 0)

    def test_no_silent_host_fallback_or_overwrite(self):
        self.git('config', '--local', 'core.hooksPath', str(self.base / 'missing-host'))
        before = (self.repo / '.git/config').read_bytes()
        self.assertNotEqual(self.setup('install', '--local-only').returncode, 0)
        self.assertEqual(before, (self.repo / '.git/config').read_bytes())

    def test_restore_with_missing_project_hook_preserves_unrelated_settings(self):
        self.install()
        self.git('config', '--local', 'fixture.unrelated', 'keep')
        (self.repo / '.githooks/pre-commit').unlink()
        self.assertEqual(self.setup('restore').returncode, 0)
        self.assertEqual(self.git('config', '--local', '--get', 'fixture.unrelated').stdout.strip(), b'keep')

    def test_binary_and_large_staged_blobs_fail_without_echo(self):
        self.stage()
        path = self.repo / 'sample.md'
        for data in (b'\x00binary-fixture', b'\xff', b'a' * (5 * 1024 * 1024 + 1)):
            path.write_bytes(data)
            self.git('add', 'sample.md')
            before = (self.repo / '.git/index').read_bytes(), path.read_bytes()
            result = self.policy('staged')
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(before, ((self.repo / '.git/index').read_bytes(), path.read_bytes()))
            self.assertNotIn(b'binary-fixture', result.stdout + result.stderr)

    def test_each_privacy_category_cli_redaction(self):
        values = ['gh' + 'p_' + 'T' * 36, 'pass' + 'word="fixture-secret"',
                  '-----BEGIN ' + 'PRIVATE KEY-----', 'fixture@' + 'private.invalid',
                  '.'.join(('10', '71', '81', '91')), '/' + 'Users' + '/fixture-person/work']
        for value in values:
            self.stage(value)
            result = self.policy('staged')
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(value.encode(), result.stdout + result.stderr)

    def test_candidate_scan_includes_untracked_without_staging(self):
        # Remove copied maintenance files to isolate the candidate under test.
        shutil.rmtree(self.repo / 'scripts')
        shutil.rmtree(self.repo / '.githooks')
        self.stage()
        (self.repo / 'untracked.md').write_text('gh' + 'p_' + 'U' * 36)
        before = (self.repo / '.git/index').read_bytes()
        self.assertNotEqual(self.policy('candidates').returncode, 0)
        self.assertEqual(before, (self.repo / '.git/index').read_bytes())
        (self.repo / 'untracked.md').write_text('clean text')
        self.assertEqual(self.policy('candidates').returncode, 0)

    def test_real_commits_clean_format_privacy(self):
        self.install()
        self.stage()
        self.assertEqual(self.git('commit', '-qm', VALID).returncode, 0)
        head = self.git('rev-parse', 'HEAD').stdout
        self.stage('safe change\n')
        self.assertNotEqual(self.git('commit', '-qm', 'bad').returncode, 0)
        self.assertEqual(head, self.git('rev-parse', 'HEAD').stdout)
        self.stage('s' + 'k-' + 'B' * 36)
        self.assertNotEqual(self.git('commit', '-qm', VALID).returncode, 0)
        self.assertEqual(head, self.git('rev-parse', 'HEAD').stdout)


if __name__ == '__main__':
    unittest.main()
