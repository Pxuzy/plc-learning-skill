#!/usr/bin/env python3
"""扫描真实 Git 对象；只报告位置和类别，不回显敏感内容。"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def git(*args: str) -> bytes:
    result = subprocess.run(['git', '--no-optional-locks', *args], capture_output=True)
    if result.returncode:
        raise ValueError('Git 对象读取失败；请核对仓库或先 fetch 所需引用')
    return result.stdout


def sha(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


class Scanner:
    def __init__(self, policy: Path):
        data = json.loads(policy.read_text(encoding='utf-8'))
        if data.get('schema') != 1:
            raise ValueError('隐私策略版本无效')
        self.identifiers = set(data['blocked_identifier_sha256'])
        self.blobs = set(data['blocked_blob_oids'])
        self.windows = set(data['blocked_code_window_sha256'])
        self.max_bytes = data['max_file_bytes']
        for values, length in [(self.identifiers, 64), (self.blobs, 40), (self.windows, 64)]:
            if not values or not all(re.fullmatch('[0-9a-f]{' + str(length) + '}', x) for x in values):
                raise ValueError('隐私指纹配置缺失或无效')
        self.errors: set[tuple[str, int, str]] = set()
        self.seen_blobs: set[str] = set()
        self.seen_trees: set[str] = set()

    def issue(self, label: str, line: int, category: str):
        # A sensitive filename itself must not be echoed into logs.
        if self.blocked_identifier(label):
            label = '[redacted-path:' + sha(label)[:12] + ']'
        label = re.sub(r'[\x00-\x1f\x7f]', '?', label)
        self.errors.add((label, line, category))

    def blocked_identifier(self, text: str) -> bool:
        return any(sha(word.lower()) in self.identifiers
                   for word in re.findall(r'[A-Za-z_][A-Za-z0-9_]*', text))

    def content(self, label: str, raw: bytes):
        if len(raw) > self.max_bytes:
            self.issue(label, 0, 'large-file')
            return
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            self.issue(label, 0, 'binary-or-non-utf8')
            return
        if '\x00' in text:
            self.issue(label, 0, 'binary-content')
            return
        for number, line in enumerate(text.splitlines(), 1):
            if self.blocked_identifier(line):
                self.issue(label, number, 'private-identifier')
            if re.search(r'(?<![\w-])(?:sk-|ghp_|github_pat_|xox[baprs]-)[A-Za-z0-9_-]{20,}', line):
                self.issue(label, number, 'credential-token')
            if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', line):
                self.issue(label, number, 'private-key')
            if re.search(r'(?i)https?://[^\s/@:]+:[^\s/@]+@', line):
                self.issue(label, number, 'url-credentials')
            if re.search(r'''(?i)\b(?:api[_-]?key|access[_-]?token|secret|password|passwd)\s*[:=]\s*["'][^"'\s]{8,}["']''', line):
                self.issue(label, number, 'literal-credential')
            if re.search(r'(?i)(?:/(?:home|Users)/[A-Za-z0-9._-]+|[A-Z]:[\\/](?:Users|Documents and Settings)[\\/][^\s\\/]+)', line):
                self.issue(label, number, 'local-home-path')
            for email in re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', line):
                domain = email.rsplit('@', 1)[1].lower()
                # Exact public GitHub service mailbox; never allow the whole domain.
                service_mailbox = email.lower() == 'noreply@github.com'
                if not service_mailbox and domain not in {'users.noreply.github.com', 'example.com', 'example.net', 'example.org'}:
                    self.issue(label, number, 'personal-email')
            candidates = re.findall(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])', line)
            candidates += [value for value in re.findall(
                r'(?<![\w:])[0-9A-Fa-f]*:[0-9A-Fa-f:]+(?:%[\w]+)?(?![\w:])', line)
                if any(char in '0123456789abcdefABCDEF' for char in value)
                and (not value.endswith(':') or value.endswith(':' * 2))]
            for value in candidates:
                try:
                    address = ipaddress.ip_address(value)
                except ValueError:
                    continue
                # RFC documentation ranges are public examples, never device addresses.
                documentation = ('192.0.2.0/24', '198.51.100.0/24',
                                 '203.0.113.0/24', '2001:db8::/32')
                if any(address.version == network.version and address in network
                       for network in map(ipaddress.ip_network, documentation)):
                    continue
                self.issue(label, number, 'ip-address')
        selected = [s.strip() for s in text.splitlines()
                    if len(s.strip()) >= 24 and re.search(r':=|\bTHEN\b|\bELSIF\b|\bCASE\b', s, re.I)]
        if any(sha('\n'.join(t)) in self.windows
               for t in zip(selected, selected[1:], selected[2:])):
            self.issue(label, 0, 'private-source-fingerprint')

    def path(self, name: str):
        p = PurePosixPath(name)
        banned = {'.git', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache',
                  '.ai', '_backup', '_preview', 'work', 'scratch', 'node_modules',
                  '.venv', 'venv', 'build', 'dist', '.idea', '.vscode', '.curator_backups'}
        suffixes = {'.zip', '.gz', '.7z', '.rar', '.tar', '.pyc', '.pyo', '.apk', '.exe',
                    '.dll', '.so', '.bin', '.db', '.sqlite', '.pdf', '.docx', '.xlsx', '.pptx',
                    '.png', '.jpg', '.jpeg', '.webp', '.p12', '.pfx', '.pem', '.key', '.log', '.tmp'}
        if self.blocked_identifier(name):
            self.issue(name, 0, 'private-filename')
        if p.is_absolute() or '..' in p.parts or banned.intersection(p.parts):
            self.issue(name, 0, 'local-or-generated-path')
        if (p.suffix.lower() in suffixes or p.name == '.env' or p.name.startswith('.env.')
                or p.name in {'id_rsa', 'id_ed25519', 'WORK_REPORT.md', 'Thumbs.db', '.DS_Store'}
                or p.name.endswith('~')):
            self.issue(name, 0, 'private-or-binary-asset')

    def blob(self, oid: str, label: str):
        if oid in self.blobs:
            self.issue(label, 0, 'known-private-blob')
        if oid not in self.seen_blobs:
            self.seen_blobs.add(oid)
            self.content(label, git('cat-file', 'blob', oid))

    def tree(self, oid: str):
        if oid in self.seen_trees:
            return
        self.seen_trees.add(oid)
        for entry in git('ls-tree', '-r', '-z', oid).split(b'\0'):
            if not entry:
                continue
            meta, path = entry.split(b'\t', 1)
            mode, kind, obj = meta.decode('ascii').split()
            name = path.decode('utf-8', errors='replace')
            self.path(name)
            if kind != 'blob' or mode not in {'100644', '100755'}:
                self.issue(name, 0, 'symlink-or-gitlink')
            else:
                self.blob(obj, name)

    def staged(self):
        self.tree(git('write-tree').decode().strip())

    def history(self, refs: list[str]):
        for ref in refs:
            if not re.fullmatch(r'[0-9a-f]{40,64}', ref):
                raise ValueError('历史扫描只接受完整 Git 对象编号')
            kind = git('cat-file', '-t', ref).decode().strip()
            while kind == 'tag':
                data = git('cat-file', 'tag', ref)
                self.content('tag:' + ref[:12], data)
                ref = data.splitlines()[0].split()[1].decode()
                kind = git('cat-file', '-t', ref).decode().strip()
            if kind != 'commit':
                raise ValueError('推送引用必须指向提交或提交标签')
            for commit in git('rev-list', ref).decode().splitlines():
                data = git('cat-file', 'commit', commit)
                self.content('commit:' + commit[:12], data)
                self.tree(commit)

    def audit(self):
        self.staged()
        for entry in git('cat-file', '--batch-all-objects', '--batch-check=%(objectname) %(objecttype)').decode().splitlines():
            oid, kind = entry.split()
            if kind == 'blob':
                self.blob(oid, 'blob:' + oid[:12])
            elif kind in {'commit', 'tag'}:
                self.content(kind + ':' + oid[:12], git('cat-file', kind, oid))
            elif kind == 'tree':
                self.tree(oid)
        for ref in git('for-each-ref', '--format=%(refname)').decode().splitlines():
            if self.blocked_identifier(ref):
                self.issue('ref:' + sha(ref)[:12], 0, 'private-ref-name')

    def message(self, path: str):
        raw = Path(path).read_bytes()
        self.content('commit-message', raw)
        text = raw.decode('utf-8').strip()
        lines = [line for line in text.splitlines() if not line.startswith('#')]
        allowed = 'feat|fix|docs|refactor|chore|merge|perf|release|revert|test|build|ci|style'
        if (not lines or len(lines[0]) > 100
                or not re.fullmatch('(' + allowed + r')\([a-z0-9][a-z0-9._-]*\): .*?[\u4e00-\u9fff].*', lines[0])
                or len(lines) < 3 or lines[1] != ''
                or not any(re.fullmatch(r'- \S.*', x) for x in lines[2:])):
            self.issue('commit-message', 0, 'message-format')

    def prepush(self, stream: str):
        lines = stream.splitlines()
        if not lines:
            raise ValueError('缺少 Git pre-push 引用输入')
        refs = []
        for line in lines:
            parts = line.split()
            if len(parts) != 4:
                raise ValueError('pre-push 引用输入格式无效')
            local_ref, new, remote_ref, old = parts
            self.content('push-ref', (local_ref + '\n' + remote_ref).encode())
            if not all(re.fullmatch(r'[0-9a-f]{40,64}', x) for x in [new, old]):
                raise ValueError('pre-push 对象编号无效')
            if set(new) == {'0'}:
                raise ValueError('禁止删除远端分支或标签')
            if not remote_ref.startswith(('refs/heads/', 'refs/tags/')):
                raise ValueError('禁止推送非分支或标签引用')
            if set(old) != {'0'}:
                git('cat-file', '-e', old)
                if remote_ref.startswith('refs/tags/') and new != old:
                    raise ValueError('禁止移动已有远端标签')
                if remote_ref.startswith('refs/heads/'):
                    result = subprocess.run(['git', 'merge-base', '--is-ancestor', old, new], capture_output=True)
                    if result.returncode:
                        raise ValueError('禁止非快进推送；请先 fetch 并合并远端变化')
            refs.append(new)
        self.history(refs)

    def report(self) -> int:
        for label, line, category in sorted(self.errors):
            print(f'BLOCK {label}:{line} [{category}]', file=sys.stderr)
        if self.errors:
            print(f'隐私门禁拒绝：{len(self.errors)} 处风险；未显示敏感值。', file=sys.stderr)
            return 1
        print('隐私门禁通过')
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy', type=Path, default=ROOT / '.githooks/privacy-policy.json')
    parser.add_argument('mode', choices=['staged', 'history', 'audit', 'message', 'pre-push'])
    parser.add_argument('targets', nargs='*')
    args = parser.parse_args()
    try:
        scanner = Scanner(args.policy)
        if args.mode == 'staged':
            scanner.staged()
        elif args.mode == 'history':
            scanner.history(args.targets or [git('rev-parse', 'HEAD').decode().strip()])
        elif args.mode == 'audit':
            scanner.audit()
        elif args.mode == 'message':
            if len(args.targets) != 1:
                raise ValueError('提交消息需要一个文件')
            scanner.message(args.targets[0])
        else:
            scanner.prepush(sys.stdin.read())
        return scanner.report()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        # Never emit subprocess stderr or arbitrary decoded content on failure.
        if isinstance(exc, ValueError) and not isinstance(exc, json.JSONDecodeError):
            print('隐私门禁拒绝：' + str(exc), file=sys.stderr)
        else:
            print('隐私门禁拒绝：策略、输入或 Git 对象无法验证。', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
