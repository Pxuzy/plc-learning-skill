#!/usr/bin/env python3
"""真实临时 Git 仓库验证暂存树、历史、消息与推送边界。"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / 'scripts' / 'git_privacy_gate.py'
POLICY = ROOT / '.githooks' / 'privacy-policy.json'


class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='plc-git-gate-', dir=os.environ.get('TMPDIR'))
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / 'repo'
        self.repo.mkdir()
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'Example Maintainer')
        self.git('config', 'user.email', 'maintainer@example.com')
        self.git('config', 'core.hooksPath', str(ROOT / '.githooks'))
        # Scanner integration tests create commits directly; hook execution has a separate case.
        self.git('config', 'core.hooksPath', str(self.repo / '.empty-hooks'))
        self.put('safe.md', '# 合成规则\n')
        self.git('add', 'safe.md')
        self.commit()

    def git(self, *args, check=True, data=None):
        result = subprocess.run(['git', '-C', str(self.repo), *args], text=True,
                                input=data, capture_output=True)
        if check:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def put(self, name, text):
        p = self.repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')

    def commit(self):
        self.git('commit', '-qm', 'test(plc-learning): 保存合成测试\n\n- 验证本地边界')
        return self.git('rev-parse', 'HEAD').stdout.strip()

    def gate(self, *args, data=None):
        self.assertTrue(GATE.exists(), '尚无 Git 隐私扫描器')
        return subprocess.run([sys.executable, '-B', str(GATE), *args], cwd=self.repo,
                              input=data, text=True, capture_output=True)

    def assert_blocked(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_clean_staged_tree_passes(self):
        self.assertEqual(self.gate('staged').returncode, 0)

    def test_scans_index_instead_of_clean_worktree(self):
        synthetic_token = 'sk' + '-' + ('A1b2C3d4' * 5)
        self.put('sample.md', synthetic_token + '\n')
        self.git('add', 'sample.md')
        self.put('sample.md', '已清理的工作区\n')
        r = self.gate('staged')
        self.assert_blocked(r)
        self.assertNotIn(synthetic_token, r.stdout + r.stderr)

    def test_ignored_and_force_added_work_is_blocked(self):
        self.put('.gitignore', 'work/\n')
        self.git('add', '.gitignore')
        self.put('work/source.st', 'output := TRUE;\n')
        self.git('add', '-f', 'work/source.st')
        self.assert_blocked(self.gate('staged'))

    def test_identifier_hash_blocks_renamed_file(self):
        token = 'SyntheticPrivateUnit'
        policy = json.loads(POLICY.read_text())
        policy['blocked_identifier_sha256'].append(hashlib.sha256(token.lower().encode()).hexdigest())
        custom = Path(self.tmp.name) / 'identifier-policy.json'
        custom.write_text(json.dumps(policy))
        self.put('generic.md', token + '\n')
        self.git('add', 'generic.md')
        self.assert_blocked(self.gate('--policy', str(custom), 'staged'))

    def test_code_fingerprint_catches_name_removed(self):
        lines = ['firstOutput := firstInput AND permitInput;',
                 'secondOutput := secondInput AND permitInput;',
                 'thirdOutput := thirdInput AND permitInput;']
        policy = json.loads(POLICY.read_text())
        policy['blocked_code_window_sha256'].append(hashlib.sha256('\n'.join(lines).encode()).hexdigest())
        custom = Path(self.tmp.name) / 'policy.json'
        custom.write_text(json.dumps(policy))
        self.put('renamed.st', '\n'.join(lines) + '\n')
        self.git('add', 'renamed.st')
        self.assert_blocked(self.gate('--policy', str(custom), 'staged'))

    def test_paths_addresses_and_email_are_blocked(self):
        samples = ['/'.join(['', 'home', 'private-person', 'sample']),
                   '.'.join(['45', '67', '89', '101']),
                   ':'.join(['2001', '4860', '', '8888']),
                   'private.person' + '@' + 'mail.invalid']
        for content in samples:
            with self.subTest(category=content.split(':')[0][:4]):
                self.put('candidate.md', content + '\n')
                self.git('add', 'candidate.md')
                self.assert_blocked(self.gate('staged'))

    def test_github_service_email_passes_without_allowing_other_mailboxes(self):
        service = 'noreply' + '@' + 'github.com'
        for mailbox, allowed in [(service, True),
                                 ('personal' + '@' + 'github.com', False),
                                 ('noreply' + '@' + 'github.com.invalid', False),
                                 ('private' + '@' + 'mail.invalid', False)]:
            with self.subTest(allowed=allowed):
                self.put('candidate.md', mailbox + '\n')
                self.git('add', 'candidate.md')
                result = self.gate('staged')
                self.assertEqual(result.returncode == 0, allowed)
                self.assertNotIn(mailbox, result.stdout + result.stderr)

    def test_github_merge_committer_passes_full_history_and_new_branch_push(self):
        env = dict(os.environ, GIT_COMMITTER_NAME='GitHub',
                   GIT_COMMITTER_EMAIL='noreply' + '@' + 'github.com')
        result = subprocess.run(['git', '-C', str(self.repo), 'commit', '--allow-empty',
                                 '-qm', 'merge(skill): 合并合成分支\n\n- 验证服务身份'],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        head = self.git('rev-parse', 'HEAD').stdout.strip()
        self.assertEqual(self.gate('history', head).returncode, 0)
        payload = f'refs/heads/topic {head} refs/heads/topic ' + '0' * 40 + '\n'
        self.assertEqual(self.gate('pre-push', data=payload).returncode, 0)

    def test_regex_and_slice_syntax_are_not_ipv6(self):
        parser_sample = 'sample = values[' + ':' * 2 + '-1]\n'
        parser_sample += "regex = r'(?" + ':' + ':' + "=|=>)'\n"
        self.put('parser.py', parser_sample)
        self.git('add', 'parser.py')
        self.assertEqual(self.gate('staged').returncode, 0)

    def test_documentation_addresses_are_public_examples(self):
        self.put('candidate.md', '192.0.2.1 198.51.100.7 203.0.113.9 2001:db8::1\n')
        self.git('add', 'candidate.md')
        self.assertEqual(self.gate('staged').returncode, 0)
        # Concrete non-documentation addresses must remain blocked.
        self.put('candidate.md', '.'.join(['10', '20', '30', '40']) + '\n')
        self.git('add', 'candidate.md')
        self.assert_blocked(self.gate('staged'))

    def test_secret_message_and_bad_style_are_blocked(self):
        p = Path(self.tmp.name) / 'message'
        p.write_text('fix(plc-learning): 修复边界\n\n- 记录变更\n')
        self.assertEqual(self.gate('message', str(p)).returncode, 0)
        for text in ['fix: english only\n', 'Merge branch feature\n',
                     'fix(plc-learning): 修复边界\n',
                     'fix(plc-learning): 修复边界\n\n- ' + 'sk' + '-' + 'B2c3D4e5' * 5]:
            p.write_text(text)
            self.assert_blocked(self.gate('message', str(p)))

    def test_deleted_secret_in_ancestor_is_blocked(self):
        self.put('temporary.md', 'ghp' + '_' + ('A1b2C3d4' * 5))
        self.git('add', 'temporary.md')
        self.commit()
        self.git('rm', '-q', 'temporary.md')
        oid = self.commit()
        self.assertEqual(self.gate('staged').returncode, 0)
        self.assert_blocked(self.gate('history', oid))
        zeros = '0' * 40
        self.assert_blocked(self.gate('pre-push', data=f'refs/heads/main {oid} refs/heads/main {zeros}\n'))

    def test_clean_new_and_fast_forward_push_pass(self):
        head = self.git('rev-parse', 'HEAD').stdout.strip()
        zeros = '0' * 40
        self.assertEqual(self.gate('pre-push', data=f'refs/heads/main {head} refs/heads/main {zeros}\n').returncode, 0)
        self.put('safe.md', '# 更新后的合成规则\n')
        self.git('add', 'safe.md')
        new = self.commit()
        self.assertEqual(self.gate('pre-push', data=f'refs/heads/main {new} refs/heads/main {head}\n').returncode, 0)

    def test_delete_nonfastforward_and_tag_move_are_blocked(self):
        old = self.git('rev-parse', 'HEAD').stdout.strip()
        self.put('safe.md', '# 更新后的合成规则\n')
        self.git('add', 'safe.md')
        new = self.commit()
        zeros = '0' * 40
        for line in [f'(delete) {zeros} refs/heads/main {new}\n',
                     f'refs/heads/main {old} refs/heads/main {new}\n',
                     f'refs/tags/v1 {new} refs/tags/v1 {old}\n']:
            self.assert_blocked(self.gate('pre-push', data=line))

    def test_crlf_fixture_keeps_bytes_and_spaces_are_still_blocked(self):
        shutil.copyfile(ROOT / '.gitattributes', self.repo / '.gitattributes')
        fixture = self.repo / 'evals/fixtures/synthetic.st'
        fixture.parent.mkdir(parents=True)
        original = b'output := TRUE;\r\n'
        fixture.write_bytes(original)
        self.git('add', '.gitattributes', 'evals/fixtures/synthetic.st')
        staged = subprocess.run(['git', '-C', str(self.repo), 'show',
                                 ':evals/fixtures/synthetic.st'], capture_output=True, check=True).stdout
        self.assertEqual(staged, original)
        self.git('diff', '--cached', '--check')
        fixture.write_bytes(b'output := TRUE; \r\n')
        self.git('add', 'evals/fixtures/synthetic.st')
        self.assertNotEqual(self.git('diff', '--cached', '--check', check=False).returncode, 0)

    def test_actual_bare_remote_and_hook_boundaries(self):
        remote = Path(self.tmp.name) / 'remote.git'
        init = subprocess.run(['git', 'init', '--bare', '-q', str(remote)], capture_output=True)
        self.assertEqual(init.returncode, 0)
        hookdir = self.repo / '.push-hooks'
        hookdir.mkdir()
        shutil.copyfile(ROOT / '.githooks/pre-push', hookdir / 'pre-push')
        (hookdir / 'pre-push').chmod(0o755)
        # The real hook resolves its dependency from the repository root.
        (self.repo / '.githooks').mkdir()
        (self.repo / 'scripts').mkdir()
        shutil.copyfile(ROOT / '.githooks/python.sh', self.repo / '.githooks/python.sh')
        shutil.copyfile(POLICY, self.repo / '.githooks/privacy-policy.json')
        shutil.copyfile(GATE, self.repo / 'scripts/git_privacy_gate.py')
        self.git('config', 'core.hooksPath', str(hookdir))
        self.git('remote', 'add', 'origin', str(remote))
        self.git('push', 'origin', 'main')
        old = self.git('rev-parse', 'HEAD').stdout.strip()
        self.put('safe.md', '# 第二个干净提交\n')
        self.git('add', 'safe.md')
        new = self.commit()
        self.git('push', 'origin', 'main')
        delete = self.git('push', 'origin', '--delete', 'main', check=False)
        self.assertNotEqual(delete.returncode, 0)
        forced = self.git('push', '--force', 'origin', old + ':refs/heads/main', check=False)
        self.assertNotEqual(forced.returncode, 0)
        self.git('tag', 'v1', old)
        self.git('push', 'origin', 'refs/tags/v1')
        self.git('tag', '-f', 'v1', new)
        moved = self.git('push', '--force', 'origin', 'refs/tags/v1', check=False)
        self.assertNotEqual(moved.returncode, 0)
        self.put('temporary.md', 'ghp' + '_' + 'D4e5F6g7' * 5)
        self.git('add', 'temporary.md')
        self.commit()
        self.git('rm', '-q', 'temporary.md')
        self.commit()
        leaked = self.git('push', 'origin', 'main', check=False)
        self.assertNotEqual(leaked.returncode, 0)
        actual = subprocess.run(['git', '--git-dir', str(remote), 'rev-parse', 'refs/heads/main'],
                                text=True, capture_output=True, check=True).stdout.strip()
        self.assertEqual(actual, new)

    def test_all_objects_audit_catches_unreachable_secret(self):
        self.git('hash-object', '-w', '--stdin', data='sk' + '-' + 'C3d4E5f6' * 5)
        self.assert_blocked(self.gate('audit'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
