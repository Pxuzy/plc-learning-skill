#!/usr/bin/env python3
"""Portable maintenance policy. Diagnostics contain categories and ordinal IDs only."""
from pathlib import Path
import ipaddress
import os
import re
import stat
import subprocess
import sys

TYPES = ('feat', 'fix', 'docs', 'refactor', 'chore', 'merge', 'perf',
         'release', 'revert', 'test', 'build', 'ci', 'style')
MAX_BYTES = 5 * 1024 * 1024
SUBJECT = re.compile(r'([a-z]+)\(([a-z]+)\): (.+)')
DENY_PATH = re.compile(
    r'(?i)(^|/)(?:\.env(?:[.-][^/]*)?|id_(?:rsa|dsa|ecdsa|ed25519)(?:$|\.)|'
    r'credentials(?:\.[^/]*)?$|service[-_]?account[^/]*\.json$|'
    r'cookies?[^/]*\.(?:json|txt)$|storage[_-]?state[^/]*$|'
    r'local\.properties$|(?:key|keystore)\.properties$|'
    r'\.ssh|\.aws|\.gnupg|personal|private|browser_profile|'
    r'node_modules|__pycache__|\.DS_Store|\.pytest_cache|\.venv|venv|\.gradle|\.kotlin|build|dist|\.cache)(?:/|$)|'
    r'(?i:\.(?:pem|key|asc|p12|pfx|jks|keystore|session|sqlite3?|db|apk|aab|'
    r'pyc|zip|7z|rar|gz|tar|png|jpe?g|gif|webp|pdf|docx?|xlsx?|mp[34]|mov)$)')
TOKENS = re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|'
                    r'sk-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16})\b')
CREDENTIAL = re.compile(
    r'''(?ix)(?:["']?)(?:password|passwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token)
    ["']?\s*[:=]\s*["']?(\$\{[A-Z_][A-Z0-9_]*\}|[^\s"',;\}\]]+)''')
EMAIL = re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}')
USER_PATH = re.compile(r'(?:/(?:home|Users)/[^\s/]+|[A-Za-z]:[\\/]Users[\\/][^\s\\/]+)')
IPV4 = re.compile(r'(?<![\w.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![\w.])')
IPV6 = re.compile(r'(?<![\w:])(?:[0-9a-fA-F]{0,4}:){2,}[0-9a-fA-F:.]*(?![\w:])')
DOC_NETS = tuple(ipaddress.ip_network(value) for value in
                 ('192.0.2.0/24', '198.51.100.0/24', '203.0.113.0/24', '2001:db8::/32'))


class PolicyError(Exception):
    """Fail closed without including subprocess output or candidate values."""


def message_errors(text):
    lines = text.splitlines()
    if not lines:
        return ['format-empty']
    match = SUBJECT.fullmatch(lines[0])
    if not match or match[1] not in TYPES:
        return ['format-subject']
    errors = []
    if len(lines[0]) > 100:
        errors.append('format-length')
    if not re.search(r'[\u4e00-\u9fff]', match[3]):
        errors.append('format-chinese')
    if len(lines) < 3 or lines[1] != '':
        errors.append('format-blank-line')
    if not any(re.fullmatch(r'- \S.*', line) for line in lines[2:]):
        errors.append('format-body')
    return errors


def public_email(value):
    local, domain = value.lower().rsplit('@', 1)
    return ((local == 'noreply' and domain == 'github.com') or
            domain in ('example.com', 'example.org', 'example.net') or
            (domain == 'users.noreply.github.com' and
             re.fullmatch(r'(?:[0-9]+\+)?[a-z0-9-]+', local) is not None))


def content_errors(data):
    if len(data) > MAX_BYTES:
        return ['size']
    try:
        value = data.decode('utf-8')
    except UnicodeDecodeError:
        return ['non-text']
    if any(ord(ch) < 32 and ch not in '\t\n\r' for ch in value):
        return ['non-text']
    errors = []
    if TOKENS.search(value):
        errors.append('token')
    for match in CREDENTIAL.finditer(value):
        candidate = match[1]
        if not (re.fullmatch(r'\$\{[A-Z_][A-Z0-9_]*\}', candidate) or
                candidate in ('REDACTED', 'PLACEHOLDER')):
            errors.append('credential')
            break
    if re.search(r'-----BEGIN (?:[A-Z0-9]+ )?PRIVATE KEY-----', value):
        errors.append('private-key')
    if any(not public_email(m[0]) for m in EMAIL.finditer(value)):
        errors.append('email')
    if USER_PATH.search(value):
        errors.append('user-path')
    for match in list(IPV4.finditer(value)) + list(IPV6.finditer(value)):
        try:
            address = ipaddress.ip_address(match[0])
        except ValueError:
            continue
        if not any(address.version == net.version and address in net for net in DOC_NETS):
            errors.append('ip')
            break
    return errors


def path_errors(name):
    errors = content_errors(os.fsencode(name))
    # Only this exact template filename is allowed; its content is still scanned.
    if name != '.env.example' and DENY_PATH.search(name):
        errors.append('material-path')
    return errors


def git(*args):
    result = subprocess.run(['git', *args], capture_output=True, timeout=30)
    if result.returncode:
        raise PolicyError('git-read')
    return result.stdout


def identities():
    return [(label, git('var', name)) for label, name in
            (('author', 'GIT_AUTHOR_IDENT'), ('committer', 'GIT_COMMITTER_IDENT'))]


def staged_findings():
    names = [os.fsdecode(raw) for raw in git('diff', '--cached', '--name-only',
             '--no-renames', '-z').split(b'\0') if raw]
    changed = set(names)
    findings = []
    for number, name in enumerate(names, 1):
        findings.extend((f'path-{number}', error) for error in path_errors(name))
    for number, record in enumerate(git('ls-files', '--stage', '-z').split(b'\0'), 1):
        if not record:
            continue
        head, path = record.split(b'\t', 1)
        mode, oid, stage = head.decode('ascii').split()
        if stage != '0':
            findings.append(('index', 'unmerged'))
        if os.fsdecode(path) not in changed:
            continue
        if mode not in ('100644', '100755'):
            findings.append((f'blob-{number}', 'non-regular'))
            continue
        if int(git('cat-file', '-s', oid)) > MAX_BYTES:
            findings.append((f'blob-{number}', 'size'))
            continue
        findings.extend((f'blob-{number}', error) for error in content_errors(git('cat-file', 'blob', oid)))
    return findings


def candidate_findings():
    # All tracked/untracked, nonignored candidates; never stage the real repository.
    names = sorted(set(git('ls-files', '-z', '--cached', '--others', '--exclude-standard').split(b'\0')) - {b''})
    findings = []
    for number, raw in enumerate(names, 1):
        name = os.fsdecode(raw)
        label = f'candidate-{number}'
        findings.extend((label, error) for error in path_errors(name))
        path = Path(name)
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(info.st_mode):
            findings.append((label, 'non-regular'))
        elif info.st_size > MAX_BYTES:
            findings.append((label, 'size'))
        else:
            findings.extend((label, error) for error in content_errors(path.read_bytes()))
    return findings


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0] not in ('staged', 'message', 'candidates'):
        raise PolicyError('usage')
    action = args[0]
    findings = []
    if action == 'message':
        if len(args) != 2:
            raise PolicyError('message-input')
        data = Path(args[1]).read_bytes()
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError:
            raise PolicyError('message-encoding') from None
        findings.extend(('message', error) for error in message_errors(text) + content_errors(data))
    else:
        if len(args) != 1:
            raise PolicyError('usage')
        findings.extend(staged_findings() if action == 'staged' else candidate_findings())
    if action != 'candidates':
        for label, data in identities():
            findings.extend((label, error) for error in content_errors(data))
    for label, error in findings[:40]:
        print(f'[project-policy] {label}: {error}', file=sys.stderr)
    if len(findings) > 40:
        print('[project-policy] additional findings omitted', file=sys.stderr)
    return int(bool(findings))


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (PolicyError, OSError, ValueError, subprocess.SubprocessError):
        print('[project-policy] check unavailable; blocked', file=sys.stderr)
        sys.exit(1)
