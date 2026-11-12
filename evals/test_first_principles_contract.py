#!/usr/bin/env python3
"""代码讲解路径契约；检查规范及示例内容，不模拟模型或 ST 编译器。"""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ASSET_KEYS = frozenset(
    {
        "SKILL.md",
        "references/code-reading.md",
        "references/local-code-explanation.md",
        "references/workflow.md",
        "references/quality-checklist.md",
        "references/teaching-from-scratch.md",
        "references/handbook-guide.md",
        "references/template-handbook.md",
        "references/example-handbook.md",
        "references/template-st-xml-framework.md",
        "references/source-archive.md",
        "references/template-index.md",
        "references/catalog.md",
        "evals/README.md",
        "evals/cases.md",
    }
)

REQUIRED_ASSET_KEYS = (
    "SKILL.md",
    "references/code-reading.md",
    "references/teaching-from-scratch.md",
    "references/handbook-guide.md",
    "references/template-handbook.md",
    "references/example-handbook.md",
    "references/template-st-xml-framework.md",
    "references/source-archive.md",
    "references/template-index.md",
    "references/catalog.md",
    "evals/README.md",
    "evals/cases.md",
)


def read_asset(asset_key: str) -> str:
    if asset_key not in ALLOWED_ASSET_KEYS:
        raise ValueError("document asset is not allowed")
    try:
        root = ROOT.resolve(strict=True)
        target = (root / asset_key).resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ValueError("document asset cannot be resolved") from error
    if not target.is_relative_to(root) or not target.is_file():
        raise ValueError("document asset must be a regular file inside the repository")
    return target.read_text(encoding="utf-8")


def section(text: str, heading: str) -> str:
    match = re.search(rf"(?m)^{re.escape(heading)}\s*$", text)
    assert match, f"缺少内容范围：{heading}"
    level = len(heading) - len(heading.lstrip("#"))
    end = re.search(rf"(?m)^#{{1,{level}}} ", text[match.end():])
    return text[match.end():match.end() + end.start() if end else len(text)]


def require(text: str, *clauses: str) -> None:
    for clause in clauses:
        assert re.search(clause, text), f"缺少实质要求：{clause}"


def ordered(text: str, *clauses: str) -> None:
    positions=[]
    for clause in clauses:
        m=re.search(clause,text)
        assert m, f"缺少顺序要求：{clause}"
        positions.append(m.start())
    assert positions==sorted(positions), "讲解顺序不正确"


def changed(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, f"变异锚点必须唯一：{old}"
    result = text.replace(old, new, 1)
    assert result != text, "变异未改变输入"
    return result


class ReadAssetBoundary(unittest.TestCase):
    def test_current_contract_documents_remain_readable(self):
        for asset_key in REQUIRED_ASSET_KEYS:
            with self.subTest(asset_key=asset_key):
                self.assertTrue(read_asset(asset_key))

    def test_rejects_absolute_and_path_aliases(self):
        rejected_keys = (
            str(ROOT / "SKILL.md"),
            "references/../SKILL.md",
            f"../{ROOT.name}/SKILL.md",
            "WORK_REPORT.md",
        )
        for asset_key in rejected_keys:
            with self.subTest(asset_key=asset_key), self.assertRaises(ValueError):
                read_asset(asset_key)

    def test_rejects_allowlisted_asset_symlink_to_outside_root(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary_directory:
            temporary_root = Path(temporary_directory)
            isolated_root = temporary_root / "isolated-root"
            isolated_root.mkdir()
            outside_document = temporary_root / "outside.md"
            outside_document.write_text("outside root", encoding="utf-8")
            (isolated_root / "SKILL.md").symlink_to(outside_document)

            with patch(f"{__name__}.ROOT", isolated_root):
                with self.assertRaises(ValueError):
                    read_asset("SKILL.md")


def shared_path(text: str) -> None:
    require(
        text,
        r"所有代码讲解[：:]问题/目标 → 已知事实与约束 → 条件/状态的必要性 → 具体输入/状态推演 → 源码因果与边界",
        r"从可见读写与控制流说明为什么需要这些条件或状态",
        r"目标只能推断时标明推断，不声称知道原作者的真实意图",
        r"A 未要求深讲时.{0,35}几个自然句.{0,35}不强制.{0,25}表格",
        r"纯事实问答.{0,25}不强行.{0,15}推演",
        r"纯源码归档.{0,25}不插入讲解",
    )


def short_if(text: str) -> None:
    require(
        text,
        r"本段要解释的问题是.{0,55}保持",
        r"已知.{0,80}没有 ELSE.{0,50}写入",
        r"因此.{0,80}xStart.{0,50}条件.{0,65}xRun.{0,40}状态",
        r"假设.{0,50}同一实例.{0,70}其他写入.{0,80}xRun = FALSE",
        r"第 1 扫描.{0,50}xStart = TRUE.{0,60}xRun.{0,30}TRUE",
        r"第 2 扫描.{0,50}xStart = FALSE.{0,70}跳过赋值.{0,40}TRUE",
        r"xStart.{0,40}为假.{0,50}不等于.{0,30}复位",
        r"其他写入点.{0,40}未知",
    )
    code = re.search(r"```st\n(.*?)\n```", text, re.S)
    assert code, "短回答示例须保留可对照的原代码"
    bare = "\n".join(line.split("//", 1)[0].rstrip() for line in code.group(1).splitlines())
    assert bare == "IF xStart THEN\n    xRun := TRUE;\nEND_IF;", bare


def interlock(text: str) -> None:
    require(
        text,
        r"问题是.{0,60}请求.{0,55}互锁.{0,45}撤销",
        r"已知.{0,90}每次.{0,80}ELSE.{0,60}FALSE",
        r"因此.{0,100}AND.{0,70}ELSE.{0,70}旧值",
        r"假设.{0,60}xRequest = TRUE.{0,60}xInterlockOK = TRUE.{0,60}xOutput.{0,40}TRUE",
        r"下一扫描.{0,60}xInterlockOK = FALSE.{0,60}ELSE.{0,60}xOutput.{0,40}FALSE",
        r"删掉.{0,30}ELSE.{0,60}保留.{0,30}TRUE",
        r"互锁来源.{0,60}未知",
    )



def confirmation_gate(text: str) -> None:
    body = section(text, "### 模式与规模选择器（先判，默认最小满足）")
    start = body.index("**源码先确认门禁")
    gate = body[start:body.index("- **A.**", start)]
    require(gate,
        r"真实工程文件.{0,30}逐字提取",
        r"文件路径.{0,40}对象/POU/程序段.{0,40}行号/范围.{0,40}无法确认",
        r"逐处核对二者一致.{0,30}实际源文件为行为依据",
        r"直接粘贴的片段按可见范围核对后直接讲解",
        r"来源仅为用户所贴片段.{0,80}不得把片段说成已从工程文件提取",
        r"未对照工程源文件.{0,25}上下文未知",
        r"只在对象/范围有歧义或用户要求先核对时暂停",
        r"独立 Markdown 核对稿",
        r"不翻译、不补全、不修正、不插入讲解或推断",
        r"明确暂停等待确认.{0,15}只有用户明确确认摘录无误后才讲解",
        r"变更.{0,15}重新核对",
        r"确认只批准源码摘录及其范围.{0,30}不代表用户确认任何程序含义",
        r"不得把创建/展示文件、沉默、继续对话或含糊反馈当作确认",
    )


class ConfirmationGateContract(unittest.TestCase):
    """静态检查条件门禁；不证明模型实际执行或语义正确。"""

    def test_current_entry_confirms_only_ambiguous_or_requested_excerpts(self):
        confirmation_gate(read_asset("SKILL.md"))

    def test_unsafe_workflow_mutations_are_rejected(self):
        text = read_asset("SKILL.md")
        for old, new in (
            ("真实工程文件", "通用范例文件"),
            ("独立 Markdown 核对稿", "聊天里的代码"),
            ("逐处核对二者一致", "无需对照二者"),
            ("未对照工程源文件", "已核验整个工程"),
            ("不得把片段说成已从工程文件提取", "可将片段视为工程提取"),
            ("只在对象/范围有歧义或用户要求先核对时暂停", "所有请求均暂停"),
            ("直接粘贴的片段按可见范围核对后直接讲解", "所有片段先等确认"),
            ("不翻译、不补全、不修正、不插入讲解或推断", "可补全并讲解"),
            ("明确暂停等待确认", "无需等待确认"),
            ("不代表用户确认任何程序含义", "同时确认全部程序含义"),
        ):
            with self.subTest(mutation=old), self.assertRaises(AssertionError):
                confirmation_gate(changed(text, old, new))


def segmented_woven(text: str) -> None:
    require(text,
        r"小段",
        r"(紧邻|紧跟|立即)",
        r"(不单列|不是单独一节|不设.{0,6}标题)",
    )


class SegmentedTeachingContract(unittest.TestCase):
    def test_entry_reference_and_template_require_segmented_woven_teaching(self):
        for key in ("SKILL.md", "references/code-reading.md", "references/template-handbook.md"):
            with self.subTest(asset=key):
                segmented_woven(read_asset(key))

    def test_removing_segment_or_inline_reason_fails_contract(self):
        text = read_asset("references/code-reading.md")
        segmented_woven(text)
        for old, new in (("小段", "整块"), ("紧邻", "之后统一"), ("不单列", "必须单列")):
            with self.subTest(mutation=old), self.assertRaises(AssertionError):
                segmented_woven(changed(text, old, new))


def segment_five_steps(text: str) -> None:
    require(text,
        r"职责",
        r"进入条件|执行条件",
        r"功能定位",
        r"整体",
        r"形象",
        r"交互",
        r"(不单列|不写成标签|不列标签|不是单独一节)",
        r"紧邻|紧跟|分小段",
    )


class SegmentStructureContract(unittest.TestCase):
    def test_every_teaching_asset_defines_the_five_step_segment(self):
        for key in ("SKILL.md", "references/code-reading.md",
                    "references/template-handbook.md", "references/teaching-from-scratch.md"):
            with self.subTest(asset=key):
                segment_five_steps(read_asset(key))

    def test_dropping_example_or_interaction_fails_contract(self):
        text = read_asset("references/code-reading.md")
        segment_five_steps(text)
        for old, new in (("形象", "其他"), ("交互", "结束"), ("整体", "局部")):
            with self.subTest(mutation=old), self.assertRaises(AssertionError):
                segment_five_steps(changed(text, old, new))


class FirstPrinciplesContract(unittest.TestCase):
    def test_entry_requires_derivation_for_all_code_routes(self):
        text = read_asset("SKILL.md")
        body = section(text, "### 模式与规模选择器（先判，默认最小满足）")
        shared_path(body)
        assert body.index("所有代码讲解") < body.index("- **A.**")
        require(body, r"\*\*A\.\*\*[^\n]*涉及代码[^\n]*上述路径", r"\*\*B\.\*\*[^\n]*上述路径")

    def test_results_only_or_c_only_mutations_are_rejected(self):
        body = section(read_asset("SKILL.md"), "### 模式与规模选择器（先判，默认最小满足）")
        shared_path(body)
        for old, new in (
            ("所有代码讲解：", "仅 C 完整手册讲解："),
            (" → 条件/状态的必要性", ""),
            ("从可见读写与控制流说明为什么需要这些条件或状态", "复述条件语法并直接给结果"),
        ):
            bad = changed(body, old, new)
            with self.subTest(mutation=old), self.assertRaises(AssertionError):
                shared_path(bad)

    def test_short_no_else_example_derives_state_and_two_scans(self):
        short_if(section(read_asset("references/code-reading.md"), "## 短代码问答（A/B）"))

    def test_short_example_mutations_keep_code_but_lose_reasoning(self):
        body = section(read_asset("references/code-reading.md"), "## 短代码问答（A/B）")
        short_if(body)
        for old, new in (
            ("因此 `xStart` 限定何时写入的条件与 `xRun` 承担跨扫描记忆的状态必须分开看。", "这是 IF 条件和 BOOL 赋值。"),
            ("第 2 扫描假设 `xStart = FALSE`，跳过赋值，`xRun` 仍为 TRUE。", "第 2 扫描结束。"),
        ):
            bad = changed(body, old, new)
            with self.subTest(mutation=old), self.assertRaises(AssertionError):
                short_if(bad)

    def test_local_interlock_derives_and_resets_output(self):
        interlock(section(read_asset("references/code-reading.md"), "## 按理解价值写说明（注释只能追加）"))

    def test_local_interlock_without_necessity_is_rejected(self):
        body = section(read_asset("references/code-reading.md"), "## 按理解价值写说明（注释只能追加）")
        interlock(body)
        bad = changed(body, "因此需要 AND 同时约束请求与许可，并用 ELSE 显式清除旧值。", "AND 是与，ELSE 是否则。")
        with self.assertRaises(AssertionError):
            interlock(bad)

    def test_deep_reading_and_teaching_share_reasoning_but_keep_evidence_boundary(self):
        text = read_asset("references/teaching-from-scratch.md")
        source = section(text, "## 源码深讲模式（读真实工程时加载）")
        require(source, r"问题.{0,40}事实.{0,40}约束.{0,45}条件.{0,30}状态.{0,40}推演", r"只知代码行为.{0,50}原作者.{0,30}意图")
        stages = section(text, "## 每阶段必备字段")
        require(stages, r"需求.{0,70}约束.{0,60}为什么需要.{0,40}条件或状态", r"先.{0,65}假设.{0,60}推演.{0,55}再.{0,35}代码增量")
        require(text, r"已知源事实 / 新设计 / 未知工艺")

    def test_handbook_template_and_example_derive_before_trace_and_source(self):
        template = read_asset("references/template-handbook.md")
        detail = section(template, "### M01 <模块名> 🔍")
        ordered(detail, r"功能定位与执行条件", r"设计依据", r"#### 2\. 源码", r"代码块整体讲解", r"形象示例", r"程序交互与段间交接")
        self.assertNotIn("**逐句看**", detail)
        sample = (ROOT / "references/example-block-handbook.md").read_text()
        ordered(sample, r"关键变量介绍", r"功能定位与执行条件", r"设计依据", r"#### 2\. 源码", r"代码块整体讲解", r"形象示例")
        require(sample, r"当前请求", r"保持", r"复位", r"未知")

    def test_code_reading_embedded_template_has_derivation_and_trace_before_code(self):
        text = read_asset("references/code-reading.md").split("## 代码解读单元模板",1)[1].split("## 小型辅助段",1)[0]
        ordered(text, r"关键变量", r"设计依据", r"#### 2\. 源码", r"代码块整体讲解", r"形象示例")
        require(text, r"假设", r"边界", r"交接")
        self.assertNotIn("**逐句看**", text)

    def test_st_object_template_derives_and_traces_before_source(self):
        text = section(read_asset("references/template-st-xml-framework.md"), "### 2.5 逐段精讲")
        for phrase in ("事实与约束", "为什么需要", "假设初值", "```text"):
            assert phrase in text, f"ST 对象模板缺少推导内容：{phrase}"
        assert text.index("事实与约束") < text.index("假设初值") < text.index("```text")
        require(text, r"原作者.{0,25}意图.{0,35}未知")

    def test_pure_archive_preserves_source_without_analysis(self):
        archive = read_asset("references/source-archive.md")
        require(archive, r"不.{0,20}(讲解|解释)", r"(原样|保真)")

    def test_reference_and_regression_indexes_register_affected_contract(self):
        require(read_asset("references/template-index.md"), r"A/B.{0,65}问题.{0,55}约束.{0,65}条件.{0,45}状态")
        for asset_key in ("references/catalog.md", "evals/README.md"):
            assert "test_first_principles_contract.py" in read_asset(asset_key), asset_key
        require(read_asset("evals/cases.md"), r"短代码.{0,60}第一性原理")


class RuntimeEditorialBoundaryContract(unittest.TestCase):
    """静态防回退：不把词命中当模型行为或 PLC 语义证明。"""
    def test_runtime_entry_does_not_assemble_old_dialogue_or_versions(self):
        entry = read_asset("SKILL.md")
        for fragment in ("用户判旧版更好时", "来自旧技能", "迁入旧技能"):
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, entry)
        body = entry.split("---", 2)[-1]
        self.assertNotRegex(body, r"\b\d+\.\d+\.\d+\b", "执行入口正文不应再引用技能版本沿革")
        self.assertIn("维护入口与模板来源核对", entry)
        self.assertIn("采用特定分支模板时只读取维护入口的来源核对要求", entry)
        self.assertIn("技能维护与成果保护", read_asset("references/workflow.md"))

    def test_templates_allow_unknown_clear_points_and_comparative_advantage(self):
        for asset in ("references/local-code-explanation.md", "references/template-handbook.md"):
            text = read_asset(asset)
            with self.subTest(asset=asset):
                self.assertIn("比较优势", text)
                self.assertIn("未知", text)
                self.assertNotIn("本段不复位要明确说由哪段清除", text)
        quality = read_asset("references/quality-checklist.md")
        self.assertRegex(quality, r"单因素|只改变一个因素")
        self.assertIn("承接", quality)
        self.assertNotIn("低于最低字数", quality)
        self.assertNotIn("最低字数要求", quality)

    def test_derivation_recipe_does_not_assume_current_implementation_is_necessary(self):
        recipe = read_asset("references/code-reading.md")
        for term in ("不变量", "当前写法", "冗余", "只改变一个因素", "状态账本", "定时状态清零"):
            with self.subTest(term=term):
                self.assertIn(term, recipe)
        self.assertIn("## Case 30", read_asset("evals/cases.md"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
