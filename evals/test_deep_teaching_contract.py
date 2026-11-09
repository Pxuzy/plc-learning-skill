#!/usr/bin/env python3
"""Regression checks for the source deep-teaching delivery contract.

The checks here are source-agnostic: they assert the six required explanation
slots, the evidence-gap marking, and the rejection of a minimal Markdown sample
that shows code without causality or cross-scan change. The sample is written
inside this file, so no user project source is stored in the package.

These are static prose contracts. Passing them does not prove that a model
explained any particular program correctly, and they never stand in for manual
block-by-block review.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"
REFERENCE = ROOT / "references" / "teaching-from-scratch.md"

SLOTS = (
    "现场/业务动作",
    "进入与退出/前置条件",
    "逐句因果解释",
    "跨扫描变量变化",
    "容易误解、执行顺序与多处写入",
    "交给哪个B块/外部对象",
)

# A synthetic teaching sample. Variable names are invented for this file and do
# not come from any user project; the point is the slot structure, not the plant.
SYNTHETIC_SAMPLE = """# 合成样例：单段步序推进

## B1 步序推进

来源定位：已确认（本文件内合成，无外部源码坐标）

**① 现场/业务动作。** 假设的工位在工件到位后把步号从 10 推进到 20，等待下游确认。

**② 进入与退出/前置条件。** 只有 `iStepAll = 10` 且 `xPartInAll` 为 TRUE 才进入；离开条件由步号改写决定。

**③ 逐句因果解释。** `IF iStepAll = 10 AND xPartInAll` 读取步号与到位位，两者同时为 TRUE 才进入；
`iStepAll := 20` 写入新步号，同一扫描后续逻辑可读到该值。

**④ 跨扫描变量变化。** 本扫描写入的 20 在下一扫描开头仍然可见，因此下一步的 `iStepAll = 20` 判断成立。

**⑤ 容易误解、执行顺序与多处写入。** 本段只写一次步号；若其他段也写 `iStepAll`，最终值取决于执行顺序。

**⑥ 交给哪个B块/外部对象。** 步号交给后续 B2 使用；下游是否读取需查调用清单。

资料缺失：本样例不含任务周期与调用顺序，未在目标平台编译或运行验证。
"""


def required_deep_teaching_slots(markdown: str) -> list[str]:
    """Return required source-explanation slots absent from a Markdown sample."""
    return [label for label in SLOTS if label not in markdown]


def slot_bodies(markdown: str) -> dict[str, str]:
    """Return each present slot label mapped to its body text."""
    found = {}
    for label in SLOTS:
        match = re.search(
            r"\*\*[①②③④⑤⑥] " + re.escape(label) + r"。\*\*(.*?)(?=\*\*[①②③④⑤⑥] |\Z)",
            markdown,
            re.S,
        )
        if match:
            found[label] = match.group(1)
    return found


def test_skill_routes_newcomer_source_reading_to_deep_contract():
    text = SKILL.read_text(encoding="utf-8")
    assert "源码深讲" in text
    assert "块级因果" in text
    assert "运行边界" in text


def test_reference_requires_six_source_explanation_slots_and_evidence_gaps():
    text = REFERENCE.read_text(encoding="utf-8")
    for phrase in (
        "现场/业务动作",
        "进入与退出/前置条件",
        "代码块整体讲解",
        "跨扫描变量变化",
        "容易误解、执行顺序与多处写入",
        "交给哪个B块/外部对象",
        "证据等级",
        "资料缺失",
    ):
        assert phrase in text, phrase


def test_reference_requires_entry_protocol_recovery_migration_and_source_readback():
    text = REFERENCE.read_text(encoding="utf-8")
    for phrase in (
        "当前可运行的调用入口",
        "所有权转移点唯一",
        "请求撤销不是接收确认",
        "恢复闭环",
        "迁移",
        "B3",
        "物料生命周期",
        "B5",
        "回读",
    ):
        assert phrase in text, phrase


def test_reference_records_target_baseline_without_fabricating_source_entry():
    text = REFERENCE.read_text(encoding="utf-8")
    for field in ("目标NJ型号", "Sysmac版本", "库解析", "任务周期", "变量/初值录入", "构建结果", "离线Trace", "参考实现/未验证"):
        assert field in text, field


def test_bad_minimal_markdown_is_rejected_for_code_without_causality_or_scan_change():
    bad = """# 坏例子\n\n```pascal\nxStart := TRUE;\n```\n\n| 变量 | 含义 |\n|---|---|\n| xStart | 启动 |\n"""
    assert re.search(r"```(?:pascal|st|iecst)\n[\s\S]*?```", bad)
    missing = required_deep_teaching_slots(bad)
    assert "逐句因果解释" in missing
    assert "跨扫描变量变化" in missing


def test_synthetic_sample_covers_every_slot_and_marks_gaps():
    assert not required_deep_teaching_slots(SYNTHETIC_SAMPLE)
    assert "资料缺失" in SYNTHETIC_SAMPLE
    assert "未在目标平台编译或运行验证" in SYNTHETIC_SAMPLE
    bodies = slot_bodies(SYNTHETIC_SAMPLE)
    assert set(bodies) == set(SLOTS)
    for label, body in bodies.items():
        assert len(re.sub(r"[`*\s|]", "", body)) >= 12, label


def test_slot_label_alone_is_not_an_explanation():
    stripped = SYNTHETIC_SAMPLE
    for label in SLOTS:
        stripped = re.sub(
            r"(\*\*[①②③④⑤⑥] " + re.escape(label) + r"。\*\*).*?(?=\*\*[①②③④⑤⑥] |\Z)",
            r"\1",
            stripped,
            flags=re.S,
        )
    # Labels remain, so a label-presence check alone would accept this sample.
    assert not required_deep_teaching_slots(stripped)
    bodies = slot_bodies(stripped)
    assert set(bodies) == set(SLOTS)
    for label, body in bodies.items():
        assert len(re.sub(r"[`*\s|]", "", body)) < 12, label


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print(f"deep teaching contract: {len(tests)} checks passed")
