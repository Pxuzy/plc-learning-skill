#!/usr/bin/env python3
"""模板权威与路由契约（S07）：单一注册源、兼容呈现与可用导航的正反向回归。"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "references" / "template-index.md"
ROUTER = ROOT / "templates" / "index.md"
CODE_TEMPLATE = ROOT / "templates" / "code-explanation.md"
NAV_TEMPLATE = ROOT / "templates" / "project-navigation.md"
BOOKSET_TEMPLATE = ROOT / "templates" / "handbook-index.md"
BOOKSET_BODY = ROOT / "references" / "template-handbook-index.md"
LOCAL_AUTHORITY = ROOT / "references" / "local-code-explanation.md"
EXPLAIN_WORKFLOW = ROOT / "references" / "workflows" / "explain-code.md"
NAV_WORKFLOW = ROOT / "references" / "workflows" / "project-navigation.md"

TEMPLATE_ID = re.compile(r"\b[A-Z][A-Z0-9_-]*@\d+\.\d+\b")


def read(path: Path) -> str:
    assert path.is_file(), f"缺少文件：{path.relative_to(ROOT)}"
    return path.read_text(encoding="utf-8")


def registry_ids(text: str) -> set[str]:
    return set(TEMPLATE_ID.findall(text))


def unregistered_ids(router_text: str, registry_text: str) -> set[str]:
    """路由文件中出现、但注册表未登记的模板 ID。"""
    return registry_ids(router_text) - registry_ids(registry_text)


def registry_row(text: str, template_id: str) -> list[str]:
    section = text.split("## 模板注册表", 1)[1].split("\n## ", 1)[0]
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and cells[0] == template_id:
            return cells
    raise AssertionError(f"注册表缺少 {template_id}")


def test_registry_is_the_single_authority():
    text = read(REGISTRY)
    assert "唯一登记" in text, "注册表须自述为唯一登记来源"
    for token in ("CODE@1.0", "NAV@1.0", "BOOKSET@1.0"):
        assert token in text, f"注册表未登记 {token}"
    assert "templates/index.md" in text, "注册表须说明 templates/index.md 只是路由"
    assert "兼容呈现" in text, "注册表须说明呈现模板为兼容呈现"


def test_router_has_no_unregistered_template_id():
    router = read(ROUTER)
    assert unregistered_ids(router, read(REGISTRY)) == set()
    assert "references/template-index.md" in router, "路由文件须指回唯一注册表"
    assert "适用条件" in router, "templates/index.md 须按适用条件路由"


def test_unregistered_id_rule_is_not_vacuous():
    router = "| CODE@1.0 | `code-explanation.md` |\n| FAKE@9.9 | `fake.md` |"
    assert unregistered_ids(router, "CODE@1.0") == {"FAKE@9.9"}


def test_bookset_has_one_body_and_an_explicit_compat_reference():
    row = registry_row(read(REGISTRY), "BOOKSET")
    assert "`references/template-handbook-index.md`" in row, "注册表须把 BOOKSET 指向单一正文"
    body = read(BOOKSET_BODY)
    assert "<!-- template-id: BOOKSET@1.0 -->" in body
    presentation = read(BOOKSET_TEMPLATE)
    assert "<!-- template-id: BOOKSET@1.0 -->" in presentation
    assert "<!-- template-compat: BOOKSET@1.0 -> references/template-handbook-index.md -->" in presentation, \
        "同版第二份文件须显式标注为单一正文的兼容呈现"
    for section in ("## 1. 阅读方式与整体框架", "## 2. 分册索引", "## 3. 跨册关系",
                    "## 4. 未知与缺口及覆盖", "## 5. 建议阅读顺序"):
        assert section in presentation, f"兼容呈现不得删除有效字段：{section}"
    for section in ("## 四、单元索引", "## 五、跨单元逻辑关系", "## 六、覆盖与缺口"):
        assert section in body, f"单一正文不得删除有效字段：{section}"


def test_code_template_is_a_compatible_presentation_of_the_authority():
    authority = read(LOCAL_AUTHORITY)
    template = read(CODE_TEMPLATE)
    assert "<!-- template-authority: references/local-code-explanation.md -->" in template
    for marker in ("### M01 ", "**一句话说清**：", "<!-- src:", "<!-- source-eof: none -->",
                   "<!-- explanation:", "<!-- unreviewed:", "// AI: ",
                   "<!-- 本段已完 -->", "<!-- 继续点：", "**批判性审查**：", "**验证状态**："):
        assert marker in template, f"兼容呈现缺少正式契约要素：{marker}"
    for meta in ("> 工程：", "> 讲解深度：", "> 讲解版式：块级", "> 模块编号："):
        assert meta in template, f"兼容呈现缺少正式元信息：{meta}"
        assert meta.split("：")[0] in authority, "元信息须来自正式权威"
    headings = ["#### 1. 功能定位与执行条件", "#### 2. 源码", "#### 3. 代码块整体讲解",
                "#### 4. 形象示例", "#### 5. 程序交互与段间交接"]
    positions = [template.find(heading) for heading in headings]
    assert all(position >= 0 for position in positions), f"五部分须为四级小节：{headings}"
    assert positions == sorted(positions), "五部分顺序须固定"
    assert re.search(r"(?m)^## 1\. 功能定位与执行条件", template) is None, "不得保留旧二级五部分"
    for field in ("处理过程", "关键逻辑", "写法好处", "状态变化"):
        assert f"**{field}**：" in template, f"整体讲解四字段须为粗体行内标签：{field}"
        assert f"### {field}" not in template, f"不得保留旧字段标题：{field}"


def test_code_template_keeps_analysis_fields():
    template = read(CODE_TEMPLATE)
    for header in ("| 变量 | 数据类型 | 方向 | 含义 | 谁写谁读 | 证据等级 |",
                   "| 进入条件 | 成立时 | 不成立时 | 依据 |",
                   "| 阶段/执行 | 输入与原状态 | 本段处理 | 执行结果 |",
                   "| 关系 | 来源 | 目标 | 关联变量 | 实际作用 |"):
        assert header in template, f"兼容呈现缺少表格契约：{header}"
    for phrase in ("请求范围内所有可读源码", "不得只摘录关键片段", "读写者和位置单独列证据",
                   "具体变量", "混合方向", "**场景设定**：", "**初始状态**：", "**理解要点**：",
                   "**交接要点**：", "**来源定位**：", "**设计依据**："):
        assert phrase in template, f"兼容呈现不得删除有效内容：{phrase}"


def resolved_links(path: Path) -> set[Path]:
    text = read(path)
    return {(path.parent / target.split("#", 1)[0]).resolve()
            for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text)
            if not target.startswith(("http://", "https://", "#", "mailto:"))}


def test_navigation_and_routing_stay_usable():
    router = read(ROUTER)
    for filename in ("project-navigation.md", "code-explanation.md", "handbook-index.md"):
        assert filename in router, f"路由缺少 {filename}"
        target = (ROUTER.parent / filename)
        assert target.is_file(), f"路由指向不存在的文件：{filename}"
    for phrase in ("用户已明确指定对象", "用户明确要求完整范围", "等待用户选择", "NAV", "CODE"):
        assert phrase in router, f"路由缺少适用条件：{phrase}"
    assert REGISTRY.resolve() in resolved_links(ROUTER), "路由文件须链回唯一注册表"
    navigation = read(NAV_WORKFLOW)
    assert "templates/index.md" in navigation and "templates/project-navigation.md" in navigation
    assert REGISTRY.resolve() in resolved_links(NAV_WORKFLOW), "导航流程须链回唯一注册表"
    explain = read(EXPLAIN_WORKFLOW)
    assert "templates/code-explanation.md" in explain
    assert LOCAL_AUTHORITY.resolve() in resolved_links(EXPLAIN_WORKFLOW), "讲解流程须链接正式输出权威"
    assert REGISTRY.resolve() in resolved_links(EXPLAIN_WORKFLOW), "讲解流程须链回唯一注册表"
    nav_template = read(NAV_TEMPLATE)
    for section in ("## 1. 输入识别", "## 4. 可选择的讲解对象", "## 5. 等待用户选择"):
        assert section in nav_template


def test_foundation_check_accepts_unified_templates():
    result = subprocess.run([sys.executable, "-B", str(ROOT / "evals" / "check_foundation.py")],
                            capture_output=True, text=True, cwd=ROOT, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def main() -> int:
    tests = [
        test_registry_is_the_single_authority,
        test_router_has_no_unregistered_template_id,
        test_unregistered_id_rule_is_not_vacuous,
        test_bookset_has_one_body_and_an_explicit_compat_reference,
        test_code_template_is_a_compatible_presentation_of_the_authority,
        test_code_template_keeps_analysis_fields,
        test_navigation_and_routing_stay_usable,
        test_foundation_check_accepts_unified_templates,
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
