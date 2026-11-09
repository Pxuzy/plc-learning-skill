#!/usr/bin/env python3
"""Optional standard-library checks for the PLC learning Skill foundation."""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "SKILL.md",
    "references/common/evidence-and-causality.md",
    "references/workflows/explain-code.md",
    "references/workflows/project-navigation.md",
    "references/vendors/README.md",
    "references/vendors/siemens/README.md",
    "references/vendors/omron/README.md",
    "references/vendors/beckhoff/README.md",
    "references/vendors/delta/README.md",
    "references/standards/README.md",
    "references/external/README.md",
    "evals/README.md",
    "templates/code-explanation.md",
    "templates/index.md",
    "templates/project-navigation.md",
    "templates/handbook-index.md",
    "scripts/validate_handbook.py",
]
errors = []

for relative in REQUIRED:
    if not (ROOT / relative).is_file():
        errors.append(f"missing required file: {relative}")

skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
match = re.match(r"\A---\n(.*?)\n---\n", skill, re.S)
if not match:
    errors.append("SKILL.md frontmatter is missing or malformed")
else:
    frontmatter = match.group(1)
    for key in ("name", "description"):
        if not re.search(rf"^{key}:\s*\S", frontmatter, re.M):
            errors.append(f"frontmatter lacks {key}")
    name = re.search(r"^name:\s*(.*?)\s*$", frontmatter, re.M)
    if not name or not re.fullmatch(r"(?=.{1,64}\Z)(?!-)(?!.*--)[a-z0-9-]+(?<!-)", name.group(1)):
        errors.append("frontmatter name is invalid")
    elif name.group(1) != ROOT.name:
        errors.append("frontmatter name must match the Skill directory")
    description = re.search(r"^description:\s*(.+)$", frontmatter, re.M)
    if description and len(description.group(1)) > 1024:
        errors.append("frontmatter description exceeds 1024 characters")

all_markdown = [p for p in ROOT.rglob("*.md") if not {".git", ".codegraph"}.intersection(p.parts)]
for source in all_markdown:
    content = source.read_text(encoding="utf-8")
    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", content):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        path = target.split("#", 1)[0]
        if path and not (source.parent / path).resolve().is_file():
            errors.append(f"broken local link in {source.relative_to(ROOT)}: {target}")

for phrase in ("不得因 Python", "不表示格式解析或产品支持", "Python 标准库"):
    if phrase.lower() not in (skill + (ROOT / "evals/README.md").read_text(encoding="utf-8")).lower():
        errors.append(f"runtime/maintenance contract missing concept: {phrase}")

workflow = (ROOT / "references/workflows/explain-code.md").read_text(encoding="utf-8").lower()
evidence = (ROOT / "references/common/evidence-and-causality.md").read_text(encoding="utf-8").lower()
evals = (ROOT / "evals/README.md").read_text(encoding="utf-8").lower()
for phrase in (
    "Ladder",
    "串联路径",
    "并联路径",
    "分支汇合",
    "裁切",
    "厂商专属指令语义",
    "不重建不可见的 IDE 网络",
):
    if phrase.lower() not in workflow:
        errors.append(f"Ladder workflow guidance missing concept: {phrase}")

for phrase in (
    "面向初学者",
    "状态条件",
    "明确标注的纸面轨迹",
    "具体初始值",
    "相关分支判断",
    "发生的写入",
    "保留值",
    "不能建立有依据的轨迹",
):
    if phrase.lower() not in workflow + "\n" + evidence:
        errors.append(f"conditional paper-trace guidance missing concept: {phrase}")

for phrase in (
    "每行对应一个具体变量",
    "不把不同变量合并成“混合方向”",
    "方向只依据该变量可见的声明",
    "不能据此反推接口方向",
):
    if phrase.lower() not in workflow + "\n" + evidence:
        errors.append(f"variable evidence guidance missing concept: {phrase}")

for phrase in ("厂商中立 Ladder 走查", "串联路径", "并联路径", "分支汇合", "未知"):
    if phrase.lower() not in evals:
        errors.append(f"manual Ladder acceptance case missing concept: {phrase}")

for phrase in ("按具体变量及声明/作用域逐项记录", "不把多个变量合并成“混合方向”"):
    if phrase.lower() not in evals:
        errors.append(f"manual variable evidence acceptance case missing concept: {phrase}")

template_path = ROOT / "templates/code-explanation.md"
if template_path.is_file():
    template = template_path.read_text(encoding="utf-8")
    sections = (
        "## 1. 功能定位与执行条件",
        "## 2. 源码",
        "## 3. 代码块整体讲解",
        "## 4. 形象示例",
        "## 5. 程序交互与段间交接",
    )
    positions = [template.find(section) for section in sections]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        errors.append("local explanation template sections missing or out of order")
    if "| 变量 | 数据类型 | 方向 | 含义 | 谁写谁读 | 证据等级 |" not in template:
        errors.append("local explanation template variable table has incorrect columns")
    for field in ("处理过程", "关键逻辑", "写法好处", "状态变化"):
        if f"### {field}" not in template:
            errors.append(f"local explanation template missing field: {field}")

template_index = ROOT / "templates/index.md"
if template_index.is_file():
    routing = template_index.read_text(encoding="utf-8")
    for template_id, relative in (
        ("CODE@1.0", "templates/code-explanation.md"),
        ("NAV@1.0", "templates/project-navigation.md"),
        ("BOOKSET@1.0", "templates/handbook-index.md"),
    ):
        source = ROOT / relative
        if template_id not in routing:
            errors.append(f"template registry missing {template_id}")
        if source.is_file() and template_id not in source.read_text(encoding="utf-8"):
            errors.append(f"template ID missing from {relative}")

if errors:
    print("Foundation checks failed:")
    print("\n".join(f"- {error}" for error in errors))
    sys.exit(1)

print(f"Foundation checks passed ({len(REQUIRED)} required files, {len(all_markdown)} Markdown files).")
