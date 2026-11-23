#!/usr/bin/env python3
"""工程读取路由契约；不证明模型行为、厂商格式解析或 PLC 运行。"""

from pathlib import Path
import re
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class ProjectReadingTests(unittest.TestCase):
    def test_input_classification_reads_plain_text_directly_before_project_recovery(self):
        skill = read("SKILL.md")
        workflow = read("references/workflows/read-project.md")
        classification = re.search(r"(?ms)^## 1\. 识别输入与适用组合\n(.*?)(?=^## 2\.)", workflow).group(1)
        self.assertIn("输入分类", classification)
        self.assertLess(classification.index("可读源码/文本"), classification.index("原生工程/容器/归档"))
        self.assertLess(classification.index("原生工程/容器/归档"), classification.index("截图/局部片段"))
        for extension in ("`.md`", "`.st`", "`.scl`"):
            self.assertIn(extension, classification)
        for requirement in ("直接读取", "不进入工程恢复", "只询问与问题相关的缺失上下文"):
            self.assertIn(requirement, classification)
        self.assertIn("直接读取用户提供的内容", skill)
        self.assertLess(skill.index("直接读取用户提供的内容"), skill.index("原生工程 / 容器 / 归档 / 解包目录 / 结构化导出"))
        self.assertIn("不走归档清点、OEM 查找或工程树恢复", skill)

    def test_input_classification_keeps_smc2_as_a_verified_specialized_route(self):
        skill = read("SKILL.md")
        workflow = read("references/workflows/read-project.md")
        classification = re.search(r"(?ms)^## 1\. 识别输入与适用组合\n(.*?)(?=^## 2\.)", workflow).group(1)
        self.assertIn("核实品牌/产品/格式/版本证据后", classification)
        self.assertIn("匹配的厂商格式方法", classification)
        self.assertIn("未知格式", classification)
        self.assertIn("最小安全清点", classification)
        self.assertIn("不猜测或标作 SMC2", classification)
        self.assertIn("已确认 Omron NJ/NX Sysmac Studio SMC2", skill)
        self.assertIn("references/omron-smc2-xml-workflow.md", skill)
        self.assertIn("SMC2 方法只用于已核实的适用组合", workflow)

    def test_unknown_native_format_uses_minimal_inventory_without_false_vendor_claim(self):
        workflow = read("references/workflows/read-project.md")
        classification = re.search(r"(?ms)^## 1\. 识别输入与适用组合\n(.*?)(?=^## 2\.)", workflow).group(1)
        for requirement in ("格式未识别", "最小安全清点", "记录限制", "请求最小必要导出"):
            self.assertIn(requirement, classification)
        self.assertNotIn("按 SMC2 处理", classification)

    def test_screenshots_and_partial_snippets_stay_within_visible_scope(self):
        workflow = read("references/workflows/read-project.md")
        classification = re.search(r"(?ms)^## 1\. 识别输入与适用组合\n(.*?)(?=^## 2\.)", workflow).group(1)
        for requirement in ("截图/局部片段", "只解释可见内容", "不做工程重建"):
            self.assertIn(requirement, classification)
        self.assertIn("粘贴片段或截图不强制走全工程恢复", workflow)

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

    def test_single_object_smc2_route_follows_oem_references_before_search(self):
        skill = read("SKILL.md")
        workflow = read("references/workflows/read-project.md")
        omron = read("references/omron-smc2-xml-workflow.md")
        route_table = skill.split("| 用户意图 / 输入 | 路由与动作 |", 1)[1].split("\n\n", 1)[0]
        routes = [
            [cell.strip() for cell in line.strip().strip("|").split("|")]
            for line in route_table.splitlines() if line.startswith("|")
        ]
        self.assertTrue(all(len(cells) == 2 for cells in routes))
        intents = [cells[0] for cells in routes]
        self.assertEqual(len(intents), len(set(intents)))
        overview_routes = [cells[1] for cells in routes if cells[0] == "先梳理整体结构"]
        self.assertEqual(overview_routes, [
            "OVR → MAP；[总览与结构地图](references/structure-mapping.md)；"
            "已确认 Omron NJ/NX SMC2 才用 [SMC2 方法](references/omron-smc2-xml-workflow.md)"
        ])
        smc2_routes = [cells[1] for cells in routes if cells[0] == "已确认 Omron NJ/NX Sysmac Studio SMC2"]
        self.assertEqual(len(smc2_routes), 1)
        self.assertIn("omron-smc2-xml-workflow.md", smc2_routes[0])
        self.assertIn("单目标优先按 OEM 引用定位", smc2_routes[0])
        self.assertIn("scripts/smc2_locate_pou.py", smc2_routes[0])
        self.assertIn("在工程读取路由确认适用组合后", smc2_routes[0])
        self.assertTrue((ROOT / "references/omron-smc2-xml-workflow.md").is_file())
        vendor_route = workflow.index("../vendors/omron/README.md")
        method_route = workflow.index("../omron-smc2-xml-workflow.md")
        safety_controls = workflow.index("通用解包仍须写入新的独立目录")
        self.assertLess(vendor_route, method_route)
        self.assertLess(method_route, safety_controls)

        for requirement in (
            "smc2_locate_pou.py",
            "--part body",
            "--part variables",
            "--include-source",
            "--fuzzy",
            "role_id",
            "StructuredTextModel",
            "XML 换行",
            "GUID",
            "SourceHolder",
            "PouBodySourceHolder",
            "reference_conflict",
            "object_not_found",
            "ambiguous_definition",
            "unsupported_layout",
            "退出码 `0`",
            "退出码 `2`",
            "不调用批量清点器",
            "不推测 schema",
            "内容指纹只核验内容形态",
        ):
            self.assertIn(requirement, omron)

    def test_smc2_optional_extraction_precedes_oem_and_source_reading(self):
        omron = read("references/omron-smc2-xml-workflow.md")
        sections = re.split(r"(?m)^## ", omron)
        general_flow = next(section for section in sections if section.startswith("一、"))
        fast_path = next(section for section in sections if section.startswith("二、"))
        general_flow = general_flow.split("```text", 1)[1].split("```", 1)[0]
        decision_flow = fast_path.split("```sh", 1)[1].split("```", 1)[0]
        for label, passage, ordered in (
            ("通用流程", general_flow, (
                "清点归档", "直接读取归档成员", "否则先受控解包一次到独立副本",
                "检查当前样本中的 .oem", "映射 .xml",
            )),
            ("单目标命令", decision_flow, (
                "scripts/smc2_locate_pou.py", "<精确FB名>", "--part body", "--include-source",
                "--part variables", "--fuzzy",
            )),
        ):
            with self.subTest(passage=label):
                if label == "通用流程":
                    self.assertIn("读取工具支持时直接读取归档成员", passage)
                for term in ordered:
                    self.assertIn(term, passage)
                positions = [passage.index(term) for term in ordered]
                self.assertEqual(positions, sorted(positions))
        self.assertIn("不先做通用清点或解包", fast_path)
        self.assertIn("完整工程范围", fast_path)
        self.assertIn("**不解包、不重建工程树、不提取程序体", omron)

    def test_smc2_fast_path_is_scoped_and_keeps_safe_fallbacks(self):
        omron = read("references/omron-smc2-xml-workflow.md")
        self.assertIn("单目标 FB/POU", omron)
        self.assertIn("目标对象", omron)
        self.assertIn("不默认", omron)
        self.assertIn("subtype", omron)
        self.assertIn("可验证回退", omron)
        self.assertIn("不得把名称当唯一键或覆盖重名候选", omron)
        self.assertIn("缺失或不唯一", omron)
        self.assertIn("单程序体请求不读取声明", omron)
        self.assertIn("即使候选唯一也不打开源码", omron)
        self.assertIn("角色按定义的直接同 namespace", omron)
        self.assertIn("`name` 仅是显示信息，允许本地化或缺失", omron)
        self.assertIn("相同角色类型出现多次时保留歧义", omron)
        self.assertIn("Holder 显示名不参与身份判定", omron)
        self.assertIn("不得把名称当唯一键或覆盖重名候选", omron)
        self.assertNotIn("角色须同时匹配 `name` 与 `type`", omron)
        self.assertNotIn("只认 `name` 与 `type` 同时为 `SourceHolder`", omron)

    def test_smc2_object_mapping_table_keeps_unverified_categories_out_of_cli_scope(self):
        omron = read("references/omron-smc2-xml-workflow.md")
        self.assertIn("定义 ID 选择 OEM 中的目标定义", omron)
        self.assertIn("角色 ID 是其直接子 `Variables`/`PouBody` 的 ID", omron)
        self.assertIn("Holder ID 只标识 Holder 实体", omron)
        self.assertIn("内容成员是经验证的 ZIP 成员路径", omron)
        self.assertIn("FC、Program、段/网络", omron)
        self.assertIn("全局变量、DataType", omron)
        self.assertIn("本 CLI 未支持", omron)
        self.assertIn("未用真实工程样本验证", read("references/vendors/omron/README.md"))
        self.assertIn("type/subtype", omron)
        self.assertIn("name → list", omron)
        self.assertIn("性能未实测", omron)
        self.assertIn("不能宣称所有查询为 O(1) 或小于 0.2 秒", omron)
        self.assertIn("单个 JSON、逐行 JSON 或连续 JSON 按样本中的真实边界解析", omron)
        self.assertIn("TXT 仅代表可见文本片段", omron)
        self.assertIn("未新增解析器", omron)

    def test_omron_classification_routes_only_the_verified_product_and_format(self):
        skill = read("SKILL.md")
        workflow = read("references/workflows/read-project.md")
        vendor = read("references/vendors/omron/README.md")
        generic = next(line for line in skill.splitlines() if line.startswith("| 原生工程 / 容器"))
        self.assertIn("references/workflows/read-project.md", generic)
        self.assertNotRegex(generic, r"vendors/omron|omron-smc2")

        route = next(line for line in workflow.splitlines() if line.startswith("欧姆龙"))
        self.assertRegex(route, r"产品线与格式.*对象类别")
        self.assertLess(route.index("../vendors/omron/README.md"), route.index("../omron-smc2-xml-workflow.md"))
        self.assertIn("不套用到其它品牌/格式", route)
        self.assertIn("不能仅凭品牌或后缀选择 SMC2", vendor)
        method_routes = [line for line in vendor.splitlines() if "../../omron-smc2-xml-workflow.md" in line]
        self.assertEqual(len(method_routes), 1)
        for requirement in ("已确认", "NJ/NX", "Sysmac Studio", "`.smc2`", "合成回归"):
            self.assertIn(requirement, method_routes[0])
        fallback = next(line for line in vendor.splitlines() if line.startswith("| 其它欧姆龙"))
        for requirement in ("含未知", "不套用 SMC2", "可读导出直接按可见代码处理"):
            self.assertIn(requirement, fallback)
        self.assertNotIn("../../omron-smc2-xml-workflow.md", fallback)

    def test_smc2_classification_covers_six_categories_and_limits_automatic_extraction(self):
        omron = read("references/omron-smc2-xml-workflow.md")
        table = re.search(r"(?m)^\| 对象类别 \|.*\n(?:\|.*\n)+", omron)
        self.assertIsNotNone(table, "须在现有对象分类表记录只读核对和自动提取范围")
        rows = [line.strip("|").split("|") for line in table.group().splitlines()[2:]]
        by_category = {cells[0].strip(): cells[1:] for cells in rows}
        categories = {
            "代码": ("`FunctionBlock`", "`Function`", "`Program`", "`PouBody`", "ST XML", "Ladder JSON"),
            "声明与变量": ("`Variables`", "局部", "全局", "归属", "组", "引用", "不能仅凭 `type`", "SLWD"),
            "数据类型": ("`DataType`", "XML", "候选"),
            "任务/程序关联": ("`NexTask`", "`NexAssociatedProgram`", "用户报告", "实际样本", "同名不能证明调度绑定"),
            "硬件配置": ("`AxisSettingEntity`", "`NexEcatConfiguration`", "用户报告", "元数据不能作为代码"),
            "组织/持有节点": ("`Group`", "`ChildEntities`", "`SourceHolder`", "不作为程序体", "Holder ID 不一定对应内容文件"),
        }
        self.assertEqual(len(rows), len(categories))
        self.assertEqual(by_category.keys(), categories.keys())
        for category, requirements in categories.items():
            with self.subTest(category=category):
                *evidence, extraction = by_category[category]
                for requirement in requirements:
                    self.assertIn(requirement, " ".join(evidence))
                if category in ("代码", "声明与变量"):
                    self.assertIn("仅单个 ST FunctionBlock", extraction)
                else:
                    self.assertEqual(extraction.strip(), "本 CLI 未支持")
        for requirement in ("分类与只读核对", "当前自动提取范围", "内容指纹", "归属", "不能仅凭 `.xml` 后缀或 `type`"):
            self.assertIn(requirement, table.group())

    def test_smc2_local_lookup_returns_to_user_selected_task(self):
        omron = read("references/omron-smc2-xml-workflow.md")
        workflow = read("references/workflows/read-project.md")
        self.assertIn("按输入形态和用户明确任务选最小读取范围", omron)
        self.assertIn("只要求提取就只提取", omron)
        self.assertIn("不因定位成功强制讲解", workflow)
        self.assertIn("只要求提取时只提取", workflow)
        self.assertIn("只有用户明确要求讲解", workflow)
        self.assertIn("A/B/C 现有讲解模板不变", omron)
        self.assertIn("单个 ST FunctionBlock", workflow)
        self.assertIn("不把待验证描述写成 CLI 支持", workflow)

    def test_reviewed_vendor_route_and_extraction_controls_are_explicit(self):
        workflow = read("references/workflows/read-project.md")
        self.assertIn("../vendors/omron/README.md", workflow)
        self.assertIn("无满足条件的工具时停止并请求已批准的解包结果或替代导出", workflow)
        self.assertIn("符号链接", workflow)
        self.assertIn("硬链接", workflow)
        self.assertIn("绝对/越界路径", workflow)
        self.assertIn("限制成员数", workflow)
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
