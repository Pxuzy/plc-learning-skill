#!/usr/bin/env python3
"""The active Git commit-msg hook enforces the repository message convention."""

import os
import shutil
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / ".githooks"


class CommitMessageHookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="commit-msg-hook-", dir=os.environ.get("TMPDIR"))
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Example Maintainer")
        self.git("config", "user.email", "maintainer@example.com")
        local_hooks = self.repo / ".githooks"
        local_hooks.mkdir()
        for name in ("commit-msg", "python.sh", "privacy-policy.json"):
            shutil.copy2(HOOKS / name, local_hooks / name)
        scripts = self.repo / "scripts"
        scripts.mkdir()
        shutil.copy2(ROOT / "scripts" / "git_privacy_gate.py", scripts / "git_privacy_gate.py")
        self.git("config", "core.hooksPath", str(local_hooks))
        self.git("config", "commit.gpgsign", "false")

    def git(self, *args, check=True):
        result = subprocess.run(["git", "-C", str(self.repo), *args], text=True, capture_output=True)
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def commit_with(self, message):
        (self.repo / "sample.md").write_text("合成样例\n", encoding="utf-8")
        self.git("add", "sample.md")
        path = Path(self.tmp.name) / "message.txt"
        path.write_text(message, encoding="utf-8")
        return self.git("-c", "commit.template=", "commit", "-F", str(path), check=False)

    def test_active_hook_accepts_conventional_chinese_commit(self):
        result = self.commit_with("feat(plc-learning): 增加提交规范门禁\n\n- 覆盖提交消息正反例\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_active_hook_rejects_invalid_commit_messages(self):
        invalid = [
            "更新规则\n\n- 说明变更\n",
            "fix(plc-learning): English only\n\n- 说明变更\n",
            "fix(PLC-learning): 修复提交格式\n\n- 说明变更\n",
            "feature(plc-learning): 使用未批准的 type\n\n- 说明变更\n",
            "fix(plc-learning): 缺少正文\n",
            "fix(plc-learning): 缺少空行\n- 说明变更\n",
            "fix(plc-learning): 修复\n\n说明没有分条\n",
        ]
        for message in invalid:
            with self.subTest(message=message.splitlines()[0]):
                result = self.commit_with(message)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse(self.git("rev-parse", "--verify", "HEAD", check=False).returncode == 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
