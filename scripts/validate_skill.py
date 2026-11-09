#!/usr/bin/env python3
"""校验 skill 结构是否符合 Agent Skills 规范与本地约定。

用法： python3 scripts/validate_skill.py [skill_dir]
退出码：0 通过，1 有错误。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from markdown_fences import parse_fences, body_view

MAX_LINES = 500
SOFT_LINES = 250
LEGACY_H2 = [
    "## When to Use",
    "## 运行前提（Prerequisites）",
    "## Quick Start",
    "## 核心流程",
    "## 讲解深度",
    "## 三维讲解：结构、工艺、代码",
    "## 代码讲解底线",
    "## 受保护的 FB/FC（密码块）",
    "## 证据与表述",
    "## 长文本分段输出",
    "## 硬约束",
    "## 常见失败与对策（Pitfalls）",
    "## 常见借口（Rationalizations）",
    "## 交付门槛（Verification）",
    "## 参考文件（References）",
]
CANONICAL_H2 = [
    "## 读者与成功标准（Reader & Success Test）",
    "## When to Use",
    "## 运行前提（Prerequisites）",
    "## Quick Start",
    "## 核心流程",
    "## 领域底线（Domain Invariants）",
    "## 交付门槛（Verification）",
    "## 参考文件（References）",
]
CATALOG = "references/catalog.md"
CATALOG_MAX_LINES = 200
def is_emoji(ch: str) -> bool:
    """按码位判断表情，避免在源码里写长串 unicode 转义区间。"""
    cp = ord(ch)
    return 0x1F300 <= cp <= 0x1FAFF or 0x2600 <= cp <= 0x27BF or 0x2B00 <= cp <= 0x2BFF
MAX_DESC = 1024
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
LINK_RE = re.compile(r"`((?:references|scripts|assets|templates|evals)/[^`\s]+)`")


def local_targets(text: str, source: str, *, include_code_paths: bool = True) -> set[str]:
    """根目录代码路径与相对 Markdown 链接；跳过示意占位符和外部地址。"""
    targets = {target for target in LINK_RE.findall(text) if "<" not in target} if include_code_paths else set()
    # Shared CommonMark parsing keeps quoted code from hiding prose links.
    lines = text.splitlines()
    blocks = parse_fences(text)
    open_lines = {block["line"] for block in blocks}
    close_lines = {block["end_line"] for block in blocks if block["closed"]}
    visible: list[str] = []
    for number, line in enumerate(lines, 1):
        in_block = any(block["line"] < number <= block["end_line"] for block in blocks)
        visible.append("" if number in open_lines or number in close_lines or in_block else line)
    prose = "\n".join(visible)
    prose = re.sub(r"(`+)(.*?)\1", "", prose)
    for target in re.findall(r"\]\(([^)\s]+)\)", prose):
        if target.startswith(("#", "/")) or re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target) or "<" in target:
            continue
        target = target.split("#", 1)[0]
        if target:
            targets.add((Path(source).parent / target).as_posix())
    return {target.split("#", 1)[0] for target in targets}


def catalog_checks(skill_dir: Path, text: str, errors: list[str]) -> None:
    """校验唯一资产登记与入口可达性，不重新登记模板版本。"""
    if CATALOG not in local_targets(text, "SKILL.md"):
        errors.append("入口缺少 catalog 路由")
    path = skill_dir / CATALOG
    if not path.is_file():
        errors.append("缺少统一资产 catalog")
        return
    catalog = path.read_text(encoding="utf-8")
    registered: set[str] = set()
    catalog_tests: set[str] = set()
    rule_ids: set[str] = set()
    resolved_root = skill_dir.resolve()
    for line in catalog.splitlines():
        if re.match(r"\| PLC-[A-Z0-9-]+\s*\|", line):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if len(cells) != 5 or not all(cells):
                errors.append("catalog 规则元信息不完整：" + line)
                continue
            rule_id = cells[0]
            if rule_id in rule_ids:
                errors.append("catalog 规则 ID 重复：" + rule_id)
            rule_ids.add(rule_id)
            for target, anchor in re.findall(r"`(evals/[^`#]+)(?:#([^`]+))?`", line):
                target_path = skill_dir / target
                if not target_path.is_file():
                    errors.append("catalog 规则证据目标不存在：" + target)
                elif anchor:
                    source = target_path.read_text(encoding="utf-8")
                    if not re.search(rf"(?m)^\s*def\s+{re.escape(anchor)}\s*\(", source):
                        errors.append("catalog 规则证据目标不存在：" + target + "#" + anchor)
            continue
        if not re.match(r"\s*\|\s*`", line):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 5 or not all(cells):
            errors.append("catalog 资产元信息不完整：" + line)
            continue
        match = re.fullmatch(r"`((?:references|scripts|evals)/[^`\s]+)`", cells[0])
        if not match:
            errors.append("catalog 资产路径格式错误：" + cells[0])
            continue
        target = match.group(1)
        if target.startswith("evals/test_"):
            catalog_tests.add(target)
        target_path = Path(target)
        resolved = (skill_dir / target_path).resolve()
        if (target_path.is_absolute() or ".." in target_path.parts or
                not target_path.parts or target_path.parts[0] not in {"references", "scripts", "evals"} or
                not resolved.is_relative_to(resolved_root / target_path.parts[0])):
            errors.append("catalog 资产路径越界或不规范：" + target)
            continue
        if target in registered:
            errors.append("catalog 重复登记资产：" + target)
        registered.add(target)
        if not (skill_dir / target).is_file():
            errors.append("catalog 登记文件不存在：" + target)
    actual = {p.relative_to(skill_dir).as_posix()
              for directory in ("references", "scripts", "evals")
              for p in (skill_dir / directory).rglob("*")
              if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}
    for directory in ("references", "scripts", "evals"):
        for candidate in (skill_dir / directory).rglob("*"):
            if candidate.is_symlink() and not candidate.resolve().is_relative_to(resolved_root / directory):
                errors.append("catalog 资产路径越界或不规范：" + candidate.relative_to(skill_dir).as_posix())
    for target in sorted(actual - registered):
        errors.append("catalog 未登记资产：" + target)
    discovered_tests = {p.relative_to(skill_dir).as_posix()
                        for p in (skill_dir / "evals").glob("test_*.py")}
    for target in sorted(discovered_tests - catalog_tests):
        errors.append("catalog 未登记 runner 测试：" + target)
    for target in sorted(catalog_tests - discovered_tests):
        errors.append("catalog 登记了 runner 未发现的测试：" + target)

    docs = {"SKILL.md": text}
    docs.update({p.relative_to(skill_dir).as_posix(): p.read_text(encoding="utf-8")
                 for p in (skill_dir / "references").rglob("*.md")})
    graph = {source: local_targets(body, source, include_code_paths=source != CATALOG)
             for source, body in docs.items()}
    for source, body in sorted(docs.items()):
        for target in sorted(local_targets(body, source)):
            if not (skill_dir / target).is_file():
                errors.append(f"引用了不存在的文件：{source} -> {target}")
    reached, pending = set(), ["SKILL.md"]
    while pending:
        source = pending.pop()
        if source in reached:
            continue
        reached.add(source)
        pending.extend(graph.get(source, set()) - reached)
    for target in sorted(set(docs) - reached):
        errors.append("参考文件从入口不可达：" + target)

    entry_rules = set(re.findall(r"\bPLC-[A-Z0-9-]+\b", text))
    catalog_rules = {line.split("|", 2)[1].strip() for line in catalog.splitlines()
                     if re.match(r"\| PLC-[A-Z0-9-]+\s*\|", line)}
    for rule in sorted(entry_rules - catalog_rules):
        errors.append("catalog 未登记入口规则：" + rule)
    for rule in sorted(catalog_rules - entry_rules):
        errors.append("入口未路由 catalog 规则：" + rule)


def parse_frontmatter(text: str) -> tuple[dict[str, str], list[str]]:
    if not text.startswith("---"):
        return {}, ["SKILL.md 缺少 YAML frontmatter"]
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, ["frontmatter 未闭合"]
    data: dict[str, str] = {}
    warnings: list[str] = []
    key = None
    for raw in parts[1].splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith((" ", "\t")):
            if key and ":" in raw:
                k, v = raw.strip().split(":", 1)
                data[f"{key}.{k}"] = v.strip().strip('"').strip("'")
            continue
        if ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        key, value = key.strip(), value.strip()
        if value.startswith("[") and key != "platforms":
            warnings.append(f"{key} 是数组；公开规范要求 string→string，但 Hermes 本地约定用列表")
        data[key] = value.strip('"').strip("'")
    return data, warnings


def strict_checks(skill_dir: Path, text: str, errors: list[str], warnings: list[str]) -> None:
    h2 = [ln.strip() for ln in body_view(text).splitlines() if ln.startswith("## ")]
    expected = CANONICAL_H2 if (skill_dir / CATALOG).is_file() else LEGACY_H2
    unknown = [h for h in h2 if h not in expected]
    if unknown:
        errors.append("strict: 出现规范外的 H2：" + "、".join(unknown))
    if [heading for heading in h2 if heading in expected] != expected:
        errors.append("strict: H2 顺序不符合入口规范")
    if expected == CANONICAL_H2 and len(text.splitlines()) > CATALOG_MAX_LINES:
        errors.append("strict: catalog 入口超过 200 行，应下沉细则至已有 reference")

    station = skill_dir / "references" / "template-station.md"
    checker = skill_dir / "scripts" / "validate_station_document.py"
    if station.exists() and checker.exists():
        code = checker.read_text(encoding="utf-8")
        block = code.split("BASE_HEADINGS = [", 1)[-1].split("]", 1)[0]
        required = re.findall(r'"(## [^"]+)"', block)
        body = "".join(ch for ch in station.read_text(encoding="utf-8") if not is_emoji(ch))
        missing = [h for h in required if h not in body]
        if missing:
            errors.append("strict: 工位模板缺少校验器要求的章节：" + "、".join(missing))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("skill_dir", nargs="?", default=".")
    ap.add_argument("--strict", action="store_true", help="检查 H2 顺序、软行数与模板/校验器标题对齐")
    args = ap.parse_args(argv)
    skill_dir = Path(args.skill_dir).resolve()
    skill_md = skill_dir / "SKILL.md"
    errors: list[str] = []
    warnings: list[str] = []

    if not skill_md.is_file():
        print(f"ERROR 找不到 {skill_md}")
        return 1

    text = skill_md.read_text(encoding="utf-8")
    lines = len(text.splitlines())
    fm, fm_warnings = parse_frontmatter(text)
    warnings.extend(fm_warnings)
    name = fm.get("name", "")
    desc = fm.get("description", "")

    if not name:
        errors.append("缺少 name")
    elif not NAME_RE.match(name):
        errors.append(f"name 不合规：{name!r}（仅小写字母、数字、连字符）")
    elif name != skill_dir.name:
        errors.append(f"name 与目录名不一致：{name!r} != {skill_dir.name!r}")

    if not desc:
        errors.append("缺少 description")
    elif len(desc) > MAX_DESC:
        errors.append(f"description 超过 {MAX_DESC} 字符：{len(desc)}")
    if desc and not desc.lower().startswith("use when"):
        warnings.append("description 未以 'Use when' 开头，触发准确性可能下降")
    if desc and len(desc) < 25:
        warnings.append("description 过短，可能缺少触发关键词")
    if desc and len(desc) > 60:
        warnings.append(f"description {len(desc)} 字符，Hermes 索引悬 60 字符，尾部触发词会丢失")

    if lines > MAX_LINES:
        errors.append(f"SKILL.md {lines} 行，超过 {MAX_LINES} 行上限")
    if args.strict and lines > SOFT_LINES:
        warnings.append(f"strict: SKILL.md {lines} 行，超过建议上限 {SOFT_LINES} 行")

    if not (skill_dir / "LICENSE").exists() and not (skill_dir / "LICENSE.txt").exists():
        if fm.get("license") or any("license" in k for k in fm):
            errors.append("声明了 license 但目录内没有 LICENSE 文件")
        else:
            warnings.append("目录内没有 LICENSE 文件")

    for target in sorted(set(LINK_RE.findall(text))):
        if "<" in target:
            continue
        if not (skill_dir / target).exists():
            errors.append(f"引用了不存在的文件：{target}")

    refs = skill_dir / "references"
    if (skill_dir / CATALOG).is_file() or "## 领域底线（Domain Invariants）" in text:
        catalog_checks(skill_dir, text, errors)
    elif refs.is_dir():
        for ref in refs.rglob("*.md"):
            rel = ref.relative_to(skill_dir).as_posix()
            if rel not in text:
                errors.append(f"参考文件未被 SKILL.md 引用（渐进加载会断链）：{rel}")

    # 若使用「标题名」式路由表，模板名必须能在参考文件中找到，防止改名后留死引用
    route = ""
    if "### 模板路由" in text:
        route = text.split("### 模板路由", 1)[1].split("\n###", 1)[0]
    template_names = re.findall(r"「([^」]+)」", route)
    if template_names and refs.is_dir():
        corpus = "\n".join(p.read_text(encoding="utf-8") for p in refs.rglob("*.md"))
        for tpl_name in template_names:
            if tpl_name not in corpus:
                warnings.append(f"路由表模板名在参考文件中找不到：{tpl_name}")

    if args.strict:
        strict_checks(skill_dir, text, errors, warnings)

    print(f"skill: {name or skill_dir.name}  lines: {lines}  desc: {len(desc)} chars")
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    if errors:
        print(f"\n失败：{len(errors)} 个错误，{len(warnings)} 个警告")
        return 1
    print(f"\n通过：0 个错误，{len(warnings)} 个警告")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
