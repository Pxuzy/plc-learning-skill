#!/usr/bin/env python3
"""保持旧测试入口；reference 从 SKILL.md 经 catalog 最多两跳可达。"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r"`references/([^`\s]+)`")


def indexed_refs() -> set[str]:
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "`references/catalog.md`" in skill, "入口缺少 catalog 路由"
    catalog = ROOT / "references" / "catalog.md"
    assert catalog.is_file(), "缺少统一资产 catalog"
    return set(LINK_RE.findall(skill + "\n" + catalog.read_text(encoding="utf-8")))


def test_every_reference_is_indexed_by_skill():
    files = {p.relative_to(ROOT / "references").as_posix()
             for p in (ROOT / "references").rglob("*.md")}
    missing = sorted(files - indexed_refs())
    assert not missing, f"未被 SKILL 索引：{'、'.join(missing)}"


def test_reference_links_never_point_to_unindexed_files():
    index = indexed_refs()
    bad: dict[str, list[str]] = {}
    for path in (ROOT / "references").rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        targets = set(LINK_RE.findall(text)) - {path.name}
        dangling = sorted(t for t in targets if t not in index)
        if dangling:
            bad[path.name] = dangling
    assert not bad, f"存在 catalog 未覆盖的引用：{bad}"


def test_skill_index_does_not_use_globs():
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert not re.search(r"`references/[^`]*\*", skill), "索引里不要用通配符，严格校验会当成真实路径"


def test_reference_anchor_links_resolve():
    bad: dict[str, list[str]] = {}
    for path in (ROOT / "references").glob("*.md"):
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"`[^`\n]*`", "", text)
        anchors = set(re.findall(r'<a id="([^\"]+)"', text))
        targets = set(re.findall(r"\]\(#([A-Za-z0-9_-]+)\)", text))
        dangling = sorted(target for target in targets if target not in anchors)
        if dangling:
            bad[path.name] = dangling
    assert not bad, f"参考文件中存在失效目录或交叉链接：{bad}"


def test_handbook_formatting_rules_route_through_indexed_guide():
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    guide = (ROOT / "references" / "handbook-guide.md").read_text(encoding="utf-8")
    assert "`references/handbook-guide.md`" in skill
    for rule in ("标题层级、表情与阅读辅助", "每个模块标题必须带一个表情", "stateDiagram-v2", "代码深度（默认）"):
        assert rule in guide, rule


def test_long_closed_structure_rule_has_one_canonical_copy():
    canonical = (ROOT / "references" / "code-reading.md").read_text(encoding="utf-8")
    handbook = (ROOT / "references" / "template-handbook.md").read_text(encoding="utf-8")
    st = (ROOT / "references" / "template-st-xml-framework.md").read_text(encoding="utf-8")
    rule = "长 IF/CASE 等闭合结构的源码保留一次，所有执行行仍须有价值的行内解释；教学小段用源码锚点和源行号范围说明各分支整体逻辑，不复制或补造另一份源码。完整性门禁仍拒绝重复、改写和漏行，详见 `references/code-reading.md`。"
    assert "长 IF/CASE 等闭合结构的源码保留一次" in canonical
    assert rule not in handbook
    assert rule not in st
    assert "长闭合结构规则" in handbook
    assert "长闭合结构规则" in st


if __name__ == "__main__":
    failures = 0
    total = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            total += 1
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    print(f"\n{total - failures}/{total} 通过")
    raise SystemExit(1 if failures else 0)
