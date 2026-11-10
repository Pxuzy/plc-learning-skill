#!/usr/bin/env python3
"""Guard the reviewed language/skeleton/distribution boundaries."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class DeliveryBoundaryTests(unittest.TestCase):
    def test_local_non_st_has_separate_route(self):
        local = (ROOT/'references/local-code-explanation.md').read_text()
        workflow = (ROOT/'references/workflow.md').read_text()
        self.assertIn('图形语言分支', local)
        self.assertIn('仅适用于 ST/SCL 文本', workflow)
        self.assertIn('不运行 ST 专用 CLI', workflow)
        self.assertIn('网络号、接点/线圈/指令', local)

    def test_skeleton_is_not_counted_as_source(self):
        entry = (ROOT/'SKILL.md').read_text()
        local = (ROOT/'references/local-code-explanation.md').read_text()
        self.assertIn('骨架仅用围栏外的行范围导航', entry)
        self.assertIn('骨架仅用围栏外的行范围导航', local)

    def test_distribution_has_own_acceptance_contract(self):
        workflow = (ROOT/'references/workflow.md').read_text()
        self.assertIn('运行包与维护仓库分别验收', workflow)
        self.assertIn('--runtime', workflow)
        self.assertIn('不得忽略包内运行资产的缺失', workflow)

if __name__ == '__main__':
    unittest.main()
