#!/usr/bin/env python3
"""工程读取路由契约；不证明模型行为、厂商格式解析或 PLC 运行。"""

from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class ProjectReadingTests(unittest.TestCase):
    def test_entry_routes_project_artifacts_without_treating_all_exports_as_omron(self):
        skill = read("SKILL.md")
        self.assertIn("references/workflows/read-project.md", skill)
        self.assertIn("品牌、产品线、格式和版本", skill)
        self.assertNotIn("| `.smc2` 或解包目录 |", skill)
        self.assertNotIn("完整工程/手册按 `Tasks → POU → Sections → 代码文件`", skill)

    def test_workflow_requires_platform_evidence_and_native_structure_before_source_mapping(self):
        workflow = read("references/workflows/read-project.md")
        stages = ["## 1. 识别输入与适用组合", "## 2. 加载匹配的品牌经验", "## 3. 恢复原生工程结构", "## 4. 映射目标源码与配置", "## 5. 追踪声明、调用与读写", "## 6. 进入讲解并记录缺口"]
        positions = [workflow.index(stage) for stage in stages]
        self.assertEqual(positions, sorted(positions))
        for requirement in ("不能仅凭扩展名", "不强套", "工程树排列不证明执行顺序", "不强制重建整棵工程树", "部分映射", "重复 ID", "孤立文件", "导出行号", "locating-and-tracing.md", "vendors/README.md"):
            self.assertIn(requirement, workflow)

    def test_vendor_experience_is_applicability_scoped_and_evidence_backed(self):
        vendors = read("references/vendors/README.md")
        for requirement in ("品牌 → 产品线 → 工程格式 → 版本", "未验证", "方法参考", "样本验证", "适用组合", "识别证据", "结构与映射", "失败与回退", "样本与验证", "已知限制", "脱敏", "不得将用户工程源码", "原始工程", "format-", "官方资料"):
            self.assertIn(requirement, vendors)
        for brand in ("siemens", "omron", "beckhoff", "delta"):
            self.assertIn(f"{brand}/README.md", vendors)
        self.assertIn("smc2", read("references/vendors/omron/README.md"))

    def test_omron_method_stays_conditional_and_does_not_override_output_routes(self):
        omron = read("references/omron-smc2-xml-workflow.md")
        for requirement in ("方法参考", "不表示", "品牌", "产品线", "版本", ".oem", "inspect_smc2_archive.py", "不重建工程树", "不提取程序体", "未提供", "workflows/read-project.md", "workflows/project-navigation.md", "local-code-explanation.md"):
            self.assertIn(requirement, omron)
        self.assertNotIn("首轮必须检查并写入 `00-项目索引.md`", omron)
        self.assertNotIn("每个独立对象单独编号生成", omron)

    def test_navigation_and_explicit_target_both_load_project_reading_when_needed(self):
        navigation = read("references/workflows/project-navigation.md")
        explanation = read("references/workflows/explain-code.md")
        self.assertIn("read-project.md", navigation)
        self.assertIn("read-project.md", explanation)
        self.assertIn("不要求重新选择", explanation)
        self.assertIn("粘贴片段", explanation)

    def test_reviewed_vendor_route_and_extraction_controls_are_explicit(self):
        workflow = read("references/workflows/read-project.md")
        self.assertIn("../vendors/omron/README.md", workflow)
        self.assertIn("无满足这些条件的工具时停在清点", workflow)
        self.assertIn("符号链接", workflow)
        self.assertIn("实际解压量", workflow)
        skill = read("SKILL.md")
        self.assertIn("仅已确认 Omron NJ/NX SMC2", skill)
        self.assertNotIn("读取 NJ/NX、SMC2、XML 与 FB/MFB 来源", skill)

    def test_project_identity_is_current_without_changing_teaching_assets(self):
        skill = read("SKILL.md")
        self.assertIn("name: plc-learning-skill\n", skill)
        self.assertTrue(read("README.md").startswith("# plc-learning-skill\n"))
        self.assertNotRegex(skill, r"(?m)^version:")
        for relative in ("CHANGELOG.md", "references/catalog.md", "references/template-index.md", "references/skill-maintenance.md"):
            self.assertNotRegex(read(relative), r"\b3\.\d+\.\d+\b", relative)
        for relative in ("references/code-reading.md", "references/locating-and-tracing.md", "references/process-and-signal-flow.md", "references/workflows/read-project.md", "templates/code-explanation.md", "scripts/check_st_logic.py"):
            self.assertTrue(read(relative), relative)

    def test_safety_contract_rejects_missing_evidence_or_forced_omron_route(self):
        original = Path.read_text
        baseline = read("SKILL.md")
        for bad in (baseline.replace("references/workflows/read-project.md", "references/workflows/not-loaded.md"), baseline + "\n| `.smc2` 或解包目录 | 按欧姆龙处理 |\n"):
            def mutated(path, *args, **kwargs):
                return bad if path == ROOT / "SKILL.md" else original(path, *args, **kwargs)
            with patch.object(Path, "read_text", mutated):
                with self.assertRaises(AssertionError):
                    self.test_entry_routes_project_artifacts_without_treating_all_exports_as_omron()


if __name__ == "__main__":
    unittest.main()
