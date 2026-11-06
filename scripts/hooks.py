#!/usr/bin/env python3
"""Local-only install/doctor/restore for the supported privacy host delegation."""
from pathlib import Path
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys

REQUIRED = ('pre-commit', 'commit-msg')
ROOT = Path(__file__).resolve().parents[1]


class SetupError(Exception):
    pass


def git(*args, optional=False):
    result = subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True, timeout=30)
    if result.returncode and not (optional and result.returncode == 1):
        raise SetupError('git configuration unavailable')
    return result.stdout.decode().strip()


def config(key, local=False):
    result = git('config', *(('--local',) if local else ()), '--get-all', key, optional=True)
    if '\n' in result:
        raise SetupError('multiple configuration values require manual resolution')
    return result or None


def resolve(value):
    path = Path(value).expanduser()
    return (ROOT / path).resolve() if not path.is_absolute() else path.resolve()


def executable(path):
    if not path.is_file() or not os.access(path, os.X_OK):
        raise SetupError('required executable missing or permissions changed')


def dependencies():
    for program in ('git', 'python3', 'sh'):
        if not shutil.which(program):
            raise SetupError('required dependency missing')
    for name in REQUIRED:
        executable(ROOT / '.githooks' / name)
    if not (ROOT / 'scripts/project_policy.py').is_file():
        raise SetupError('project policy missing')


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def host_contract(host):
    if host == (ROOT / '.githooks').resolve():
        raise SetupError('recursive host configuration')
    pinned = {}
    for name in REQUIRED:
        hook = host / name
        executable(hook)
        lines = hook.read_text().splitlines()
        # Recognize the supported host adapter, not arbitrary scripts that might not delegate.
        commands = [shlex.split(line) for line in lines if line.startswith('exec ')]
        if len(commands) != 1 or len(commands[0]) < 3:
            raise SetupError('unsupported host; delegation must be verified before installation')
        command = commands[0]
        executable(Path(command[1]))
        gate = Path(command[2])
        if not gate.is_absolute() or not gate.is_file():
            raise SetupError('host implementation missing')
        source = gate.read_text()
        if 'privacy.originalHooksPath' not in source or 'legacy_hook' not in source:
            raise SetupError('host delegation contract unavailable')
        pinned[str(hook)] = fingerprint(hook)
        pinned[str(gate)] = fingerprint(gate)
        # The supported installed privacy adapter uses these local dependencies.
        # The simple contract stub used in tests does not claim to be this adapter.
        if 'def precommit_scan()' in source:
            for dependency in ('gitleaks', 'pre-commit'):
                executable(Path.home() / '.local/bin' / dependency)
            for dependency in ('policy.json', 'secrets.toml', 'gitleaks.toml',
                               'pre-commit-config.yaml', 'check_commit_message.py'):
                path = gate.parent / dependency
                if not path.is_file():
                    raise SetupError('host dependency missing')
                pinned[str(path)] = fingerprint(path)
    return pinned


def locations():
    common = resolve(git('rev-parse', '--git-common-dir'))
    return common, common / 'plc-hooks-state.json'


def diagnose(state):
    dependencies()
    expected = str(ROOT / '.githooks')
    if state['target'] != expected or config(state['key'], local=True) != expected:
        raise SetupError('owned configuration drift')
    if state['mode'] == 'host':
        if resolve(config('core.hooksPath') or '') != Path(state['host']):
            raise SetupError('effective host drift')
        if host_contract(Path(state['host'])) != state['pins']:
            raise SetupError('host implementation drift')
        if resolve(config('privacy.originalHooksPath') or '') != (ROOT / '.githooks').resolve():
            raise SetupError('missing or recursive delegation')
    elif resolve(config('core.hooksPath') or '') != (ROOT / '.githooks').resolve():
        raise SetupError('effective local hook drift')


def install(local_only):
    dependencies()
    common, state_path = locations()
    if state_path.exists():
        state = json.loads(state_path.read_text())
        diagnose(state)
        print('hooks: already installed; doctor OK')
        return
    effective = config('core.hooksPath')
    target = str(ROOT / '.githooks')
    state = {'target': target, 'key': 'privacy.originalHooksPath', 'mode': 'host'}
    if effective:
        if local_only:
            raise SetupError('host configured; local-only fallback refused')
        host = resolve(effective)
        pins = host_contract(host)
        existing = config('privacy.originalHooksPath')
        if existing:
            raise SetupError('pre-existing delegate must be preserved; installation refused')
        legacy = common / 'hooks'
        if any(p.is_file() and not p.name.endswith('.sample') and os.access(p, os.X_OK) for p in legacy.glob('*')):
            raise SetupError('pre-existing default hooks require manual chain design')
        state.update(host=str(host), pins=pins)
    else:
        if not local_only:
            raise SetupError('no host detected; explicit local-only mode required')
        if config('privacy.originalHooksPath'):
            raise SetupError('pre-existing delegate requires manual resolution')
        if any(p.is_file() and not p.name.endswith('.sample') and os.access(p, os.X_OK) for p in (common / 'hooks').glob('*')):
            raise SetupError('pre-existing default hooks must be preserved')
        state.update(key='core.hooksPath', mode='local-only')
    state['previous'] = config(state['key'], local=True)
    # Back up before mutation. This nonversioned state contains local paths, not project docs.
    state['config_backup'] = (common / 'config').read_text()
    with open(state_path, 'x', opener=lambda name, flags: os.open(name, flags, 0o600)) as backup:
        backup.write(json.dumps(state, indent=2) + '\n')
    try:
        git('config', '--local', state['key'], target)
        diagnose(state)
    except (SetupError, OSError, ValueError):
        if state['previous'] is None:
            git('config', '--local', '--unset-all', state['key'], optional=True)
        else:
            git('config', '--local', state['key'], state['previous'])
        state_path.unlink()
        raise
    print('hooks: installed locally; doctor OK; mode=' + state['mode'])


def main():
    args = sys.argv[1:]
    if args not in (['install'], ['install', '--local-only'], ['doctor'], ['restore']):
        raise SetupError('usage: hooks.py install [--local-only] | doctor | restore')
    if args[0] != 'restore':
        dependencies()
    if resolve(git('rev-parse', '--show-toplevel')) != ROOT:
        raise SetupError('installer must belong to this repository')
    _, path = locations()
    if args[0] == 'install':
        install('--local-only' in args)
        return
    if not path.is_file():
        raise SetupError('installation state missing; install or inspect chain')
    state = json.loads(path.read_text())
    if args[0] == 'doctor':
        diagnose(state)
        print('doctor: OK; project gates reachable; mode=' + state['mode'])
        print('doctor: identity/first-commit approval not certified')
        if state['mode'] == 'host':
            print('doctor: host may skip a missing delegate; rerun after configuration changes')
    else:
        # Restore only our own setting; never replace the whole config backup.
        if config(state['key'], local=True) != state['target']:
            raise SetupError('owned setting drift; refusing destructive restoration')
        if state['previous'] is None:
            git('config', '--local', '--unset-all', state['key'])
        else:
            git('config', '--local', state['key'], state['previous'])
        path.unlink()
        print('hooks: owned local setting restored; unrelated settings preserved')


if __name__ == '__main__':
    try:
        main()
    except (SetupError, OSError, ValueError, KeyError, subprocess.SubprocessError):
        print('hooks: blocked; dependency, chain, permission or configuration check failed; see maintenance guide',
              file=sys.stderr)
        sys.exit(1)
