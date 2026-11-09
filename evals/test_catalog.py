#!/usr/bin/env python3
"""入口渐进加载与 catalog 资产契约；仅在临时目录变异，不触碰用户产物。"""

import re
import runpy
import shutil
import tempfile
import unittest
from pathlib import Path

from _harness import run

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_skill.py"
CATALOG = "references/catalog.md"
ASSET_RE = re.compile(r"`((?:references|scripts|evals)/[^`\s]+)`")
RULES = {
    "PLC-SAFE-READONLY": "references/template-index.md",
    "PLC-EVIDENCE-LEVELS": "references/structure-mapping.md",
    "PLC-ST-LAYERS": "references/code-reading.md",
    "PLC-CODE-SOURCE": "references/code-reading.md",
    "PLC-COMMENT-VALUE": "references/comment-quality.md",
    "PLC-TEMPLATE-COMPOSE": "references/template-index.md",
    "PLC-DELIVERY-VERIFY": "references/workflow.md",
    "PLC-ORDER-SCOPE": "references/teaching-from-scratch.md",
}


def catalog_text():
    path = ROOT / CATALOG
    assert path.is_file(), "缺少统一资产 catalog"
    return path.read_text(encoding="utf-8")


def asset_rows(text):
    return [line for line in text.splitlines() if re.match(r"\| `(?:references|scripts|evals)/", line)]


class CatalogTests(unittest.TestCase):
    def test_catalog_covers_actual_assets_with_metadata(self):
        rows = asset_rows(catalog_text())
        paths = [ASSET_RE.search(row).group(1) for row in rows]
        actual = {p.relative_to(ROOT).as_posix()
                  for directory in ("references", "scripts", "evals")
                  for p in (ROOT / directory).rglob("*")
                  if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}
        self.assertEqual(set(paths), actual)
        self.assertEqual(len(paths), len(set(paths)), "资产不得重复登记")
        for row in rows:
            cells = [cell.strip() for cell in row.strip("|").split("|")]
            self.assertEqual(len(cells), 5, row)
            self.assertTrue(all(cells), row)

    def test_entry_routes_without_duplicating_inventory(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        limit = runpy.run_path(str(VALIDATOR)).get("CATALOG_MAX_LINES", 200)
        self.assertLessEqual(len(text.splitlines()), limit)
        self.assertIn(f"`{CATALOG}`", text)
        self.assertFalse(asset_rows(text), "入口不重复 catalog 的资产登记行")
        self.assertFalse({p for p in ASSET_RE.findall(text) if p.startswith("evals/")})
        maintenance = text.split("### 维护入口（仅修改技能时加载）", 1)[1].split("## 参考文件", 1)[0]
        for route in ("references/workflow.md", "技能维护与成果保护", "技能维护回归"):
            self.assertIn(route, maintenance)
        workflow = (ROOT / "references/workflow.md").read_text(encoding="utf-8")
        regression = workflow.split("### 技能维护回归", 1)[1].split("### ", 1)[0]
        self.assertIn("evals/run.py", regression)
        self.assertNotIn("| 脚本 |", text)
        self.assertNotIn("| 版本与回归 |", text)

    def test_rule_ids_route_to_authority_and_executable_evidence(self):
        catalog = catalog_text()
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        for rule, authority in RULES.items():
            self.assertIn(rule, skill)
            rows = [line for line in catalog.splitlines() if line.startswith(f"| {rule} |")]
            self.assertEqual(len(rows), 1, rule)
            self.assertIn(f"`{authority}`", rows[0])
            self.assertRegex(rows[0], r"`scripts/[^`]+\.py`")
            tests = re.findall(r"`(evals/test_[^`#]+\.py)#([^`]+)`", rows[0])
            self.assertGreaterEqual(len(tests), 2, f"{rule} 需要正/负用例")
            for path, name in tests:
                self.assertIn(f"def {name}(", (ROOT / path).read_text(encoding="utf-8"))

    def fixture(self):
        self.addCleanup(lambda: self.tmp.cleanup())
        self.tmp = tempfile.TemporaryDirectory(prefix="plc-catalog-")
        root = Path(self.tmp.name) / ROOT.name
        root.mkdir()
        for directory in ("references", "scripts", "evals"):
            shutil.copytree(ROOT / directory, root / directory, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for name in ("SKILL.md", "LICENSE", "CHANGELOG.md"):
            shutil.copy2(ROOT / name, root / name)
        return root

    def check(self, root, expected, message=""):
        result = run(VALIDATOR, str(root), "--strict")
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertIn(message, result.stdout)

    def test_strict_accepts_catalog_routed_references(self):
        root = self.fixture()
        self.check(root, 0, "0 个错误，0 个警告")

    def test_catalog_registration_without_topic_navigation_is_orphan(self):
        root = self.fixture()
        (root / "references/orphan-probe.md").write_text("# 没有导航\n", encoding="utf-8")
        path = root / CATALOG
        path.write_text(path.read_text(encoding="utf-8") +
                        "\n| `references/orphan-probe.md` | 仅登记 | 注册 | 人工 | 当前 |\n", encoding="utf-8")
        self.check(root, 1, "参考文件从入口不可达：references/orphan-probe.md")

    def test_catalog_explicit_topic_link_is_navigation(self):
        root = self.fixture()
        (root / "references/topic-probe.md").write_text("# 专题\n", encoding="utf-8")
        path = root / CATALOG
        path.write_text(path.read_text(encoding="utf-8") +
                        "\n| `references/topic-probe.md` | [夹紧信号证据专题](topic-probe.md) | 追踪夹紧信号 | 人工 | 当前 |\n", encoding="utf-8")
        self.check(root, 0, "0 个错误，0 个警告")

    def test_catalog_symlink_cannot_cross_declared_directory_inside_root(self):
        root = self.fixture()
        (root / "references/alias.md").symlink_to("../scripts/validate_skill.py")
        path = root / CATALOG
        path.write_text(path.read_text(encoding="utf-8") +
                        "\n| `references/alias.md` | [别名](alias.md) | 按需 | 人工 | 当前 |\n", encoding="utf-8")
        self.check(root, 1, "catalog 资产路径越界或不规范：references/alias.md")

    def test_catalog_unknown_directory_rows_are_not_silently_ignored(self):
        root = self.fixture()
        (root / "assets").mkdir()
        (root / "assets/x.md").write_text("# 错误目录中的真实文件\n", encoding="utf-8")
        path = root / CATALOG
        path.write_text(path.read_text(encoding="utf-8") +
                        "\n| `assets/x.md` | 错误目录 | 按需 | 人工 | 当前 |\n", encoding="utf-8")
        self.check(root, 1, "catalog 资产路径格式错误：`assets/x.md`")

    def test_actual_skill_passes_strict_validation(self):
        self.check(ROOT, 0, "0 个错误，0 个警告")

    def test_inline_fence_text_cannot_hide_later_broken_link(self):
        targets = runpy.run_path(str(VALIDATOR))["local_targets"](
            "正文提及 ```pascal。\n[坏链](missing-fence.md)\n正文提及 ```st。\n", "references/handbook-guide.md")
        self.assertIn("references/missing-fence.md", targets)
        root = self.fixture()
        path = root / "references" / "handbook-guide.md"
        path.write_text(path.read_text(encoding="utf-8") +
                        "\n说明中提及 ```pascal 而非围栏。\n[坏链](missing-fence.md)\n", encoding="utf-8")
        self.check(root, 1, "references/handbook-guide.md -> references/missing-fence.md")

    def test_real_entry_mutation_is_rejected(self):
        root = self.fixture()
        path = root / "SKILL.md"
        path.write_text(path.read_text(encoding="utf-8") +
                        "\n## 额外章节\n[缺失](references/nope.md)\n", encoding="utf-8")
        result = run(VALIDATOR, str(root), "--strict")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("H2", result.stdout)
        self.assertIn("references/nope.md", result.stdout)

    def test_extra_h2_is_one_error_without_duplicate_order_error(self):
        root = self.fixture()
        path = root / "SKILL.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n## 额外章节\n", encoding="utf-8")
        result = run(VALIDATOR, str(root), "--strict")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(result.stdout.count("strict: 出现规范外的 H2"), 1)
        self.assertNotIn("strict: H2 顺序不符合", result.stdout)

    def test_rule_id_registration_is_bidirectional(self):
        root = self.fixture()
        path = root / "SKILL.md"
        path.write_text(path.read_text(encoding="utf-8") +
                        "\n- **PLC-UNREGISTERED-RULE**：新规则。\n", encoding="utf-8")
        self.check(root, 1, "catalog 未登记入口规则：PLC-UNREGISTERED-RULE")

    def test_catalog_rejects_rule_without_metadata(self):
        root = self.fixture()
        path = root / CATALOG
        path.write_text(path.read_text(encoding="utf-8") +
                        "\n| PLC-INVALID-RULE | 缺少字段 |\n", encoding="utf-8")
        self.check(root, 1, "catalog 规则元信息不完整")

    def test_catalog_rejects_duplicate_rule_ids(self):
        root = self.fixture()
        catalog = root / "references/catalog.md"
        text = catalog.read_text(encoding="utf-8")
        row = next(line for line in text.splitlines() if line.startswith("| PLC-SAFE-READONLY |"))
        catalog.write_text(text.replace(row, row + "\n" + row, 1), encoding="utf-8")
        self.check(root, 1, "catalog 规则 ID 重复")

    def test_catalog_rule_evidence_targets_must_exist(self):
        root = self.fixture()
        catalog = root / "references/catalog.md"
        text = catalog.read_text(encoding="utf-8").replace(
            "evals/test_handbook_validator.py#test_read_only_safety_boundary_is_allowed",
            "evals/missing-test.py#test_read_only_safety_boundary_is_allowed", 1)
        catalog.write_text(text, encoding="utf-8")
        self.check(root, 1, "catalog 规则证据目标不存在")

    def test_catalog_test_registration_matches_runner_discovery(self):
        root = self.fixture()
        catalog = root / "references/catalog.md"
        text = catalog.read_text(encoding="utf-8")
        text = "\n".join(line for line in text.splitlines()
                          if not line.startswith("| `evals/test_block_layout.py`")) + "\n"
        catalog.write_text(text, encoding="utf-8")
        self.check(root, 1, "catalog 未登记 runner 测试")

    def test_skill_frontmatter_has_no_personal_author_identity(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = text.split("---", 2)[1]
        self.assertNotRegex(frontmatter, r"(?m)^author\s*:")

    def test_catalog_asset_cannot_escape_declared_directory(self):
        root = self.fixture()
        path = root / CATALOG
        path.write_text(path.read_text(encoding="utf-8") +
                        "\n| `references/../SKILL.md` | 越界资产 | 按需 | 人工 | 当前 |\n", encoding="utf-8")
        self.check(root, 1, "catalog 资产路径越界或不规范")

    def test_catalog_asset_symlink_cannot_escape_skill_root(self):
        root = self.fixture()
        outside = Path(self.tmp.name) / "outside.md"
        outside.write_text("outside\n", encoding="utf-8")
        (root / "references" / "escape.md").symlink_to(outside)
        path = root / CATALOG
        path.write_text(path.read_text(encoding="utf-8") +
                        "\n| `references/escape.md` | 越界链接 | 按需 | 人工 | 当前 |\n", encoding="utf-8")
        self.check(root, 1, "catalog 资产路径越界或不规范")

    def test_unregistered_asset_is_rejected(self):
        root = self.fixture()
        for directory, filename in (("references", "new-rule.md"), ("scripts", "new-tool.py"), ("evals", "new-case.json")):
            with self.subTest(directory=directory):
                path = root / directory / filename
                path.write_text("新增资产\n", encoding="utf-8")
                try:
                    self.check(root, 1, f"catalog 未登记资产：{directory}/{filename}")
                finally:
                    path.unlink()

    def test_catalog_missing_target_is_rejected(self):
        root = self.fixture()
        path = root / CATALOG
        path.write_text(path.read_text(encoding="utf-8") +
                        "\n| `references/missing.md` | 规则 | 按需 | 人工 | 当前 |\n", encoding="utf-8")
        self.check(root, 1, "catalog 登记文件不存在：references/missing.md")

    def test_missing_catalog_route_is_rejected(self):
        root = self.fixture()
        path = root / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn(f"`{CATALOG}`", text)
        path.write_text(text.replace(f"`{CATALOG}`", "资产目录"), encoding="utf-8")
        self.check(root, 1, "入口缺少 catalog 路由")

    def test_broken_reference_link_is_rejected(self):
        root = self.fixture()
        path = root / "references" / "workflow.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n见 `references/missing.md`。\n", encoding="utf-8")
        self.check(root, 1, "引用了不存在的文件：references/workflow.md -> references/missing.md")

    def test_broken_relative_markdown_link_is_rejected(self):
        root = self.fixture()
        path = root / "references" / "workflow.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n见 [流程](missing.md)。\n", encoding="utf-8")
        self.check(root, 1, "引用了不存在的文件：references/workflow.md -> references/missing.md")


if __name__ == "__main__":
    unittest.main(verbosity=2)
