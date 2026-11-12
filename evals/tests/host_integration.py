"""Explicit actual inherited-host integration; uses only an isolated scratch repo."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = 'fixture@' + 'example.com'
VALID = 'docs(repo): 验证门禁\n\n- 合成测试\n'


def main():
    probe = subprocess.run(['git', 'config', '--get', 'core.hooksPath'],
                           capture_output=True, check=False)
    inherited = probe.stdout.decode().strip()
    if probe.returncode or not inherited:
        print('skipped: 本机未配置 core.hooksPath（无宿主钩子链可集成）')
        return 77
    host = Path(inherited).expanduser().resolve()
    delegate = subprocess.run(['git', 'config', '--get', 'privacy.originalHooksPath'],
                              capture_output=True, check=False).stdout.decode().strip()
    if delegate and Path(delegate).expanduser().resolve() != (ROOT / '.githooks').resolve():
        print('skipped: 宿主委托指向另一个检出（' + delegate + '），本仓库未安装自己的钩子链')
        return 77
    with tempfile.TemporaryDirectory(prefix='plc-actual-host-') as folder:
        scratch = Path(folder)
        repo = scratch / 'repo'
        repo.mkdir()
        for name in ('scripts', '.githooks'):
            shutil.copytree(ROOT / name, repo / name)
        env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1',
                   GIT_AUTHOR_NAME='Public Fixture', GIT_COMMITTER_NAME='Public Fixture',
                   GIT_AUTHOR_EMAIL=PUBLIC, GIT_COMMITTER_EMAIL=PUBLIC,
                   GIT_TRACE2_EVENT=str(scratch / 'trace.jsonl'), PYTHONDONTWRITEBYTECODE='1')
        results = []

        def command(label, args, expect=0):
            result = subprocess.run(args, cwd=repo, env=env, capture_output=True, timeout=60)
            results.append({'label': label, 'exit': result.returncode})
            if (result.returncode == 0) != (expect == 0):
                raise RuntimeError('unexpected integration result: ' + label + '; exit=' + str(result.returncode))
            return result

        def git(label, *args, expect=0):
            return command(label, ['git', *args], expect)

        git('init', 'init', '-q')
        git('host-local-fixture', 'config', '--local', 'core.hooksPath', str(host))
        command('install-host-chain', [sys.executable, '-B', str(repo / 'scripts/hooks.py'), 'install'])
        config_before = (repo / '.git/config').read_bytes()
        command('idempotent-install', [sys.executable, '-B', str(repo / 'scripts/hooks.py'), 'install'])
        assert config_before == (repo / '.git/config').read_bytes(), 'idempotent config'
        command('doctor', [sys.executable, '-B', str(repo / 'scripts/hooks.py'), 'doctor'])
        candidate = repo / 'sample.md'
        candidate.write_text('clean synthetic documentation\n')
        git('stage-clean', 'add', 'sample.md')
        git('clean-commit', 'commit', '-qm', VALID)
        head = git('read-head', 'rev-parse', 'HEAD').stdout
        candidate.write_text('next clean change\n')
        git('stage-next', 'add', 'sample.md')
        git('invalid-format-blocked', 'commit', '-qm', 'invalid', expect=1)
        assert git('unchanged-head-format', 'rev-parse', 'HEAD').stdout == head
        # Host allows digits in scopes; project requirement intentionally requires letters only.
        git('project-specific-format-blocked', 'commit', '-qm', VALID.replace('(repo)', '(repo1)'), expect=1)
        sensitive = 'gh' + 'p_' + 'H' * 36
        candidate.write_text(sensitive)
        git('stage-private', 'add', 'sample.md')
        candidate.write_text('clean worktree\n')
        index = git('index-entries-before', 'ls-files', '--stage', '-z').stdout
        result = git('staged-privacy-blocked', 'commit', '-qm', VALID, expect=1)
        assert sensitive.encode() not in result.stdout + result.stderr
        assert git('index-entries-after', 'ls-files', '--stage', '-z').stdout == index, 'staged objects changed during actual git commit'
        assert candidate.read_text() == 'clean worktree\n'
        assert git('unchanged-head-privacy', 'rev-parse', 'HEAD').stdout == head
        candidate.write_text('third clean change\n')
        git('stage-metadata-case', 'add', 'sample.md')
        env['GIT_AUTHOR_EMAIL'] = 'fixture@' + 'private.invalid'
        result = git('metadata-blocked', 'commit', '-qm', VALID, expect=1)
        assert env['GIT_AUTHOR_EMAIL'].encode() not in result.stdout + result.stderr
        assert git('unchanged-head-metadata', 'rev-parse', 'HEAD').stdout == head
        trace = (scratch / 'trace.jsonl').read_text()
        for name in ('pre-commit', 'commit-msg'):
            assert str(host / name) in trace, 'actual host hook trace: ' + name
        print(json.dumps({'actual_host': True, 'trace_confirmed_host_hooks': ['pre-commit', 'commit-msg'],
                          'results': results, 'fixture_identity': 'public example-domain fixture',
                          'real_project_history_modified': False}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        code = main()
        if code:
            sys.exit(code)
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
    except AssertionError as error:
        print('integration assertion: ' + str(error), file=sys.stderr)
        sys.exit(1)
    except (OSError, ValueError, subprocess.SubprocessError):
        print('actual-host integration failed; inspect local chain without exposing candidate values', file=sys.stderr)
        sys.exit(1)
