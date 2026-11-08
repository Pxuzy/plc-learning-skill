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

    def test_foundation_checks_chinese_contracts(self):
        result = run(sys.executable, '-B', ROOT / 'evals/check_foundation.py', cwd=ROOT)
        output = result.stdout.decode(errors='replace') + result.stderr.decode(errors='replace')
        self.assertEqual(result.returncode, 0, output)

    def test_foundation_ignores_generated_codegraph_markdown(self):
        with tempfile.TemporaryDirectory(prefix='plc-foundation-test-') as temporary:
            fixture = Path(temporary) / ROOT.name
            result = run('git', 'ls-files', '--', '*.md', cwd=ROOT)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
            tracked_markdown = result.stdout.decode().splitlines()

            for relative in tracked_markdown:
                source = ROOT / relative
                if source.is_file():
                    target = fixture / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)

            template = fixture / 'templates/code-explanation.md'
            template.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / 'templates/code-explanation.md', template)
            for name in ('index.md', 'project-navigation.md', 'handbook-index.md'):
                target = fixture / 'templates' / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / 'templates' / name, target)
            navigation = fixture / 'references/workflows/project-navigation.md'
            navigation.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / 'references/workflows/project-navigation.md', navigation)
            plan_stub = fixture / 'docs/plans/2026-11-08-plc-skill-requirements-alignment.md'
            plan_stub.parent.mkdir(parents=True, exist_ok=True)
            plan_stub.write_text('', encoding='utf-8')

            checker = fixture / 'evals/check_foundation.py'
            checker.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / 'evals/check_foundation.py', checker)
            validator = fixture / 'scripts/validate_handbook.py'
            validator.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / 'scripts/validate_handbook.py', validator)
            generated = fixture / '.codegraph/index.md'
            generated.parent.mkdir(parents=True, exist_ok=True)
            generated.write_text('[generated](missing-file.md)\n', encoding='utf-8')

            result = run(sys.executable, '-B', checker, cwd=fixture)
            output = result.stdout.decode(errors='replace') + result.stderr.decode(errors='replace')
            self.assertEqual(result.returncode, 0, output)

    def test_code_explanation_template_contract(self):
        template = ROOT / 'templates/code-explanation.md'
        self.assertTrue(template.is_file(), 'local code explanation template must exist')
        content = template.read_text(encoding='utf-8')
        sections = (
            '## 1. 功能定位与执行条件',
            '## 2. 源码',
            '## 3. 代码块整体讲解',
            '## 4. 形象示例',
            '## 5. 程序交互与段间交接',
        )
        positions = [content.index(section) for section in sections]
        self.assertEqual(positions, sorted(positions), 'five-part template sections must stay ordered')
        self.assertIn('| 变量 | 数据类型 | 方向 | 含义 | 谁写谁读 | 证据等级 |', content)
        for field in ('处理过程', '关键逻辑', '写法好处', '状态变化'):
            self.assertIn(f'### {field}', content)

    def test_project_navigation_template_contract(self):
        template = ROOT / 'templates/project-navigation.md'
        self.assertTrue(template.is_file(), 'project navigation template must exist')
        content = template.read_text(encoding='utf-8')
        sections = (
            '## 1. 输入识别',
            '## 2. 一页总览',
            '## 3. 工程结构地图',
            '## 4. 可选择的讲解对象',
            '## 5. 等待用户选择',
            '## 6. 多册手册索引（按需）',
        )
        positions = [content.index(section) for section in sections]
        self.assertEqual(positions, sorted(positions), 'navigation template sections must stay ordered')
        self.assertIn('| 编号 | 对象/范围 | 可见证据 | 依赖或上下文 | 状态 |', content)
        for phrase in ('品牌/产品线', '版本线索', '保留工程原有层级', '等待用户选择', '不要提前生成完整手册'):
            self.assertIn(phrase, content)

    def test_template_index_routes_navigation_explanation_and_bookset(self):
        index = (ROOT / 'templates/index.md').read_text(encoding='utf-8')
        for identifier in ('NAV@1.0', 'CODE@1.0', 'BOOKSET@1.0'):
            self.assertIn(identifier, index)
        for filename in ('project-navigation.md', 'code-explanation.md', 'handbook-index.md'):
            self.assertIn(filename, index)
        self.assertIn('用户已明确指定对象', index)
        self.assertIn('用户明确要求完整范围', index)

        bookset = (ROOT / 'templates/handbook-index.md').read_text(encoding='utf-8')
        self.assertIn('| 册号 | 手册文件 | 对象范围 | 覆盖状态 | 来源证据 |', bookset)
        self.assertIn('跨册关系', bookset)
        self.assertIn('未知与缺口', bookset)

    def test_annotation_policy_defaults_to_selective_value_add_comments(self):
        skill = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
        workflow = (ROOT / 'references/workflows/explain-code.md').read_text(encoding='utf-8')
        self.assertIn('默认不添加 `AI:` 行内注释', skill)
        self.assertIn('默认不加 `AI:` 行内注释', workflow)
        self.assertIn('常见条件判断、直接赋值', workflow)
        self.assertIn('源码/正文表达', skill)
        self.assertIn('没有具体且有意义的信息损失', skill)

    def test_variable_evidence_is_recorded_per_declaration(self):
        skill = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
        workflow = (ROOT / 'references/workflows/explain-code.md').read_text(encoding='utf-8')
        evidence = (ROOT / 'references/common/evidence-and-causality.md').read_text(encoding='utf-8')
        template = (ROOT / 'templates/code-explanation.md').read_text(encoding='utf-8')
        evals = (ROOT / 'evals/README.md').read_text(encoding='utf-8')
        for content in (skill, workflow, evidence, template, evals):
            self.assertIn('具体变量', content)
            self.assertIn('方向', content)
            self.assertIn('声明', content)
            self.assertIn('混合方向', content)
        self.assertIn('读取/写入角色', workflow)
        self.assertIn('读写者和位置单独列证据', template)

    def test_detailed_explanation_presents_auditable_source(self):
        skill = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
        workflow = (ROOT / 'references/workflows/explain-code.md').read_text(encoding='utf-8')
        template = (ROOT / 'templates/code-explanation.md').read_text(encoding='utf-8')
        for content in (skill, workflow, template):
            self.assertIn('请求范围内所有可读源码', content)
            self.assertIn('不得只摘录关键片段', content)
        self.assertIn('固定的五个章节名称与顺序', skill)
        self.assertIn('形象示例与程序交互分开', skill)

    def test_complex_project_learning_route_is_user_selectable(self):
        skill = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
        navigation = ROOT / 'references/workflows/project-navigation.md'
        self.assertTrue(navigation.is_file(), 'project navigation workflow must exist')
        workflow = navigation.read_text(encoding='utf-8')
        for content in (skill, workflow):
            self.assertIn('先盘点', content)
            self.assertIn('可选择的讲解对象', content)
            self.assertIn('等待用户选择', content)
            self.assertIn('Markdown', content)
        self.assertIn('project-navigation.md', skill)
        self.assertIn('templates/index.md', skill)

    def test_detailed_handbook_is_delivered_as_markdown_file(self):
        skill = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
        workflow = (ROOT / 'references/workflows/explain-code.md').read_text(encoding='utf-8')
        navigation = (ROOT / 'references/workflows/project-navigation.md').read_text(encoding='utf-8')
        for content in (skill, workflow, navigation):
            self.assertIn('完整手册写为独立的 `.md` 文件', content)
            self.assertIn('返回文件路径或链接', content)
        self.assertIn('用户指定路径优先', workflow)
        self.assertIn('不得覆盖已有文件', workflow)
        self.assertIn('评测输出留在仓库外隔离目录', workflow)

    def test_requirements_snapshot_uses_selective_annotation_rule(self):
        requirements = (ROOT / 'docs/requirements.md').read_text(encoding='utf-8')
        self.assertIn('逐行核对源码与讲解', requirements)
        self.assertIn('按信息量选择性追加', requirements)
        self.assertIn('每条候选注释执行删除测试', requirements)
        self.assertNotIn('尽可能每条非空代码行加简短、准确的 `AI:` 注释', requirements)

    def test_skill_metadata_matches_directory_and_describes_use(self):
        content = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
        frontmatter = content.split('---', 2)[1]
        values = dict(line.split(':', 1) for line in frontmatter.splitlines() if ':' in line)
        self.assertEqual(values['name'].strip(), ROOT.name)
        description = values['description'].strip()
        self.assertLessEqual(len(description), 1024)
        self.assertIn('解释', description)
        self.assertIn('当用户', description)
        self.assertIn('品牌', description)
        self.assertIn('工程', description)
        self.assertIn('Markdown', description)

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

    def test_sensitive_paths_are_rejected(self):
        name = 'gh' + 'p_' + 'R' * 36 + '.md'
        self.stage(name=name)
        result = self.policy('staged')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(name.encode(), result.stdout + result.stderr)
        self.git('rm', '--cached', '--', name)

    def test_symlink_staged_is_rejected(self):
        link = self.repo / 'link'
        try:
            link.symlink_to('sample.md')
        except (OSError, NotImplementedError):
            self.skipTest('symbolic links are unavailable in this environment')
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
        result = run(sys.executable, '-B', POLICY, 'staged', cwd=self.base, env=self.env)
        self.assertNotEqual(result.returncode, 0)

    @unittest.skipUnless(os.name == 'posix', 'POSIX shell and executable-bit semantics required')
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

    @unittest.skipUnless(os.name == 'posix', 'POSIX shell and executable-bit semantics required')
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

    @unittest.skipUnless(os.name == 'posix', 'POSIX shell and executable-bit semantics required')
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

    def test_candidate_scan_handles_deleted_tracked_files_without_index_changes(self):
        tracked = self.stage(name='deleted.md')
        tracked.unlink()
        before = (self.repo / '.git/index').read_bytes()
        result = self.policy('candidates')
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(before, (self.repo / '.git/index').read_bytes())

        protected = self.stage(name='.env')
        protected.unlink()
        before = (self.repo / '.git/index').read_bytes()
        result = self.policy('candidates')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'material-path', result.stderr)
        self.assertNotIn(b'FileNotFoundError', result.stderr)
        self.assertEqual(before, (self.repo / '.git/index').read_bytes())

    @unittest.skipUnless(os.name == 'posix', 'POSIX shell and executable-bit semantics required')
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
