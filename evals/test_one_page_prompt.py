#!/usr/bin/env python3
"""一页模板必须自带"源码不得删减"契约，且结构固定到可照抄。"""
from pathlib import Path
import re, sys, unittest

ROOT = Path(__file__).resolve().parents[1]
TEXT = (ROOT / "references/one-page-prompt.md").read_text(encoding="utf-8")


class OnePagePromptTests(unittest.TestCase):
    def test_source_fidelity_is_the_first_hard_rule(self):
        rules = TEXT.split("【硬规则】", 1)[1].split("【输出格式】", 1)[0]
        first = [l for l in rules.splitlines() if l.strip().startswith("1.")]
        self.assertTrue(first, "硬规则第一条缺失")
        self.assertIn("完整", first[0])
        self.assertRegex(first[0], r"不删行|不截短")

    def test_rule_count_stays_small_enough_for_weak_models(self):
        rules = TEXT.split("【硬规则】", 1)[1].split("【输出格式】", 1)[0]
        numbered = re.findall(r"(?m)^\d+\.", rules)
        self.assertLessEqual(len(numbered), 6, "规则超过 6 条，弱模型会漏做")

    def test_forbidden_omission_markers_are_named(self):
        for marker in ("...", "略", "其余同上"):
            self.assertIn(marker, TEXT)

    def test_fixed_skeleton_is_copyable(self):
        for heading in ("## 整体功能与关键变量", "**控制目标**", "<a id=\"m01\"></a>", "### M01",
                        "#### 1. 功能定位与执行条件", "#### 2. 源码",
                        "#### 3. 代码块整体讲解", "#### 4. 形象示例", "#### 5. 程序交互与段间交接"):
            self.assertIn(heading, TEXT, heading)

    def test_mode_b_keeps_original_source_and_five_parts(self):
        self.assertIn("模式 B", TEXT)
        self.assertIn("默认追加短业务尾注", TEXT)
        self.assertIn("完整原码与原注释", TEXT)
        self.assertIn("要求原样源码时不追加", TEXT)
        self.assertIn("五部分", TEXT)

    def test_fallback_shares_local_metadata_and_variable_schema(self):
        skeleton = TEXT.split("【输出格式】", 1)[1].split("【代码】", 1)[0]
        local = (ROOT / "references/local-code-explanation.md").read_text(encoding="utf-8")
        header = "| 变量 | 数据类型 | 方向 | 含义 | 谁写谁读 | 证据等级 |"
        self.assertIn(header, skeleton)
        self.assertIn(header, local)
        for metadata in ("# <对象与范围>", "> 工程：", "> 讲解深度：", "> 讲解版式：", "> 模块编号：", "**一句话说清**", "**来源定位**"):
            self.assertIn(metadata, skeleton)
        self.assertIn("长 IF/CASE 保持闭合", TEXT)
        self.assertIn("不机械拆断", TEXT)
        self.assertIn("第三部分", TEXT.split("【硬规则】", 1)[1].split("【输出格式】", 1)[0])

    def test_four_field_instructions_and_skeleton_are_unique(self):
        rules = TEXT.split("【硬规则】", 1)[1].split("【输出格式】", 1)[0]
        skeleton = TEXT.split("【输出格式】", 1)[1].split("【代码】", 1)[0]
        for label in ("处理过程", "关键逻辑", "写法好处", "状态变化"):
            with self.subTest(label=label):
                self.assertEqual(rules.count(f"**{label}**"), 1)
                self.assertEqual(skeleton.count(f"**{label}**"), 1)

    def test_no_vague_phrases_inside_template(self):
        banned = ("执行判断", "条件判断", "满足条件则赋值", "条件很重要", "变量变化了", "详见代码")
        # 模板会引用这些词作为反例，只检查骨架正文部分
        skeleton = TEXT.split("【输出格式】", 1)[1].split("【代码】", 1)[0]
        for phrase in banned:
            self.assertNotIn(phrase, skeleton, f"骨架里混入空话：{phrase}")

    def test_oversize_instruction_forbids_deletion(self):
        self.assertIn("拆成多段", TEXT)
        self.assertRegex(TEXT, r"严禁删除|不删行")
        # 校验器报错同样不得暗示"删"
        gate = (ROOT / "scripts/block_layout.py").read_text(encoding="utf-8")
        block = gate.split("行上限", 1)[1][:120]
        self.assertIn("严禁", block)


if __name__ == "__main__":
    unittest.main(verbosity=2)
