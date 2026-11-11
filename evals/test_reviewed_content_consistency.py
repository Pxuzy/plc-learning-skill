#!/usr/bin/env python3
"""审查修复后的内容一致性回归：S01/S02/S05/S06/S08/S09/D01。

只检查技能内规范与模板的相互一致性，不调用模型、不访问网络。
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(*parts: str) -> str:
    return ROOT.joinpath(*parts).read_text(encoding="utf-8")


def test_s01_default_comment_mode_matches_official_reference() -> None:
    """质量清单与代码阅读规则都应与正式局部参考一致：默认业务短尾注，原样请求才不追加。"""
    checklist = read("references", "quality-checklist.md")
    code_reading = read("references", "code-reading.md")

    assert "默认追加简洁业务短尾注" in checklist
    assert "用户要求原样源码时不追加" in checklist
    assert "默认原码" not in checklist
    assert "默认不追加教学注释" not in checklist

    assert "B 默认业务短尾注" in code_reading
    assert "B 默认原码" not in code_reading


def test_s02_direction_placeholder_is_declaration_not_read_write_role() -> None:
    """方向列只能填声明方向；读写角色归“谁写谁读”列。"""
    prompt = read("references", "one-page-prompt.md")

    assert "| 变量 | 数据类型 | 方向 | 含义 | 谁写谁读 | 证据等级 |" in prompt
    assert "<声明方向；无声明填未知>" in prompt
    assert "<读/写>" not in prompt


def test_s05_protected_block_tool_advice_is_vendor_neutral() -> None:
    """通用受保护块流程不得把单一品牌 IDE 写成通用步骤。"""
    checklist = read("references", "quality-checklist.md")

    assert "对应厂商工程软件" in checklist
    assert "Sysmac Studio" not in checklist


def test_s06_sfc_and_stl_are_disambiguated_by_vendor_and_language() -> None:
    """SFC 按步/转移切分；STL 可能是指令表或步进指令，先按品牌与语言标识消歧。"""
    code_reading = read("references", "code-reading.md")

    assert "SFC/STL 不可合并" in code_reading
    assert "SFC 一个步或一个转移" in code_reading
    assert "IL/STL/AWL" in code_reading
    assert "按品牌" in code_reading
    assert "消歧" in code_reading


def test_s08_heading_levels_are_defined_relative_to_parent() -> None:
    """单对象 M###/五部分 ####；多工位 W###/M####/五部分 #####。"""
    guide = read("references", "handbook-guide.md")
    template = read("references", "template-handbook.md")

    assert "单对象模块一律 `###`" in guide
    assert "工位 `###`、模块 `####`、五部分 `#####`" in guide
    assert "不得让模块与所在工位同级" in guide

    assert "`#### M01`" in template
    assert "`##### 1～5`" in template
    assert "整体降一级" in template
    assert "#### W01 源码块覆盖清单" in template


def test_s09_group_by_native_objects_station_only_with_evidence() -> None:
    """完整工程按原生对象与有证据的业务关系分组，工位只在工程实际存在时使用。"""
    guide = read("references", "handbook-guide.md")
    template = read("references", "template-handbook.md")

    assert "按工程原生层级" in guide
    assert "工位层只在工程实际存在工位" in guide
    assert "不造工位地图" in guide

    assert "工程实际存在工位时才插入工位层" in template
    assert "<任务 → 工位 POU → 段>" not in template
    assert "工位" in template  # 保留制造产线的工位分析能力


def test_d01_readme_version_claim_matches_current_policy() -> None:
    """README 不得再声称与已移除的 SKILL.md version 字段同步。"""
    readme = read("README.md")

    assert "frontmatter 的 `version` 同步" not in readme
    assert "按“未发布”维护" in readme
    assert "不自动升版" in readme


def test_entry_has_portable_metadata_and_independent_rules() -> None:
    text = read('SKILL.md')
    frontmatter = dict(line.split(':', 1) for line in text.split('---', 2)[1].splitlines() if ':' in line)
    frontmatter = {key: value.strip().strip('"') for key, value in frontmatter.items()}
    assert set(frontmatter) == {'name', 'description'}, frontmatter.keys()
    assert frontmatter['description'] == '学习、讲解或分析 PLC 程序、工程结构、互锁与状态机，阅读 ST、梯形图等代码时使用。'
    assert read('LICENSE').strip()
    assert '用户说' not in text
    assert '用户否掉的是' not in text
    assert '只有用户明确否定' not in text
    for heading in ('**讲解稿的语言/教学审查', '**讲解稿的精简修订'):
        assert heading in text


def test_documents_do_not_embed_conversation_history() -> None:
    """检查实际文档而非报告；条件规则和PLC扫描时间线不属于对话记录。"""
    forbidden = ["本" + "用户", "用户会" + "立刻回", "会被回" + "“",
                 "本机上" + "一轮遗漏", "此前发出" + "的真实源码小样",
                 "此前你" + "正在设计", "用户再" + "次说",
                 "你的模板同时也要" + "满足我上面的要求"]
    for path in sorted(ROOT.rglob("*.md")):
        if any(part.startswith(".") for part in path.relative_to(ROOT).parts):
            continue
        text = path.read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in text, f"{path.relative_to(ROOT)}: conversation-history residue"


def main() -> int:
    tests = [
        test_s01_default_comment_mode_matches_official_reference,
        test_s02_direction_placeholder_is_declaration_not_read_write_role,
        test_s05_protected_block_tool_advice_is_vendor_neutral,
        test_s06_sfc_and_stl_are_disambiguated_by_vendor_and_language,
        test_s08_heading_levels_are_defined_relative_to_parent,
        test_s09_group_by_native_objects_station_only_with_evidence,
        test_d01_readme_version_claim_matches_current_policy,
        test_entry_has_portable_metadata_and_independent_rules,
        test_documents_do_not_embed_conversation_history,
    ]
    failed = 0
    for test in tests:
        try:
            test()
        except Exception as exc:
            failed += 1
            print(f"FAIL {test.__name__}: {exc}")
        else:
            print(f"PASS {test.__name__}")
    print(f"{len(tests) - failed}/{len(tests)} passed")
    return int(failed > 0)


if __name__ == "__main__":
    raise SystemExit(main())
