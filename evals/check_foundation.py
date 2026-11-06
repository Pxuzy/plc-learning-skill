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
    "references/vendors/README.md",
    "references/vendors/siemens/README.md",
    "references/vendors/omron/README.md",
    "references/vendors/beckhoff/README.md",
    "references/vendors/delta/README.md",
    "references/standards/README.md",
    "references/external/README.md",
    "evals/README.md",
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

all_markdown = [p for p in ROOT.rglob("*.md") if ".git" not in p.parts]
for source in all_markdown:
    content = source.read_text(encoding="utf-8")
    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", content):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        path = target.split("#", 1)[0]
        if path and not (source.parent / path).resolve().is_file():
            errors.append(f"broken local link in {source.relative_to(ROOT)}: {target}")

for phrase in ("must never block", "vendor folders indicate", "Python"):
    if phrase.lower() not in (skill + (ROOT / "evals/README.md").read_text(encoding="utf-8")).lower():
        errors.append(f"runtime/maintenance contract missing phrase: {phrase}")

workflow = (ROOT / "references/workflows/explain-code.md").read_text(encoding="utf-8").lower()
evidence = (ROOT / "references/common/evidence-and-causality.md").read_text(encoding="utf-8").lower()
evals = (ROOT / "evals/README.md").read_text(encoding="utf-8").lower()
for phrase in (
    "ladder",
    "series",
    "parallel",
    "branch joins",
    "cropped",
    "vendor-specific instruction semantics",
    "do not reconstruct an unseen ide",
):
    if phrase not in workflow:
        errors.append(f"Ladder workflow guidance missing phrase: {phrase}")

for phrase in (
    "detailed beginner",
    "state conditions",
    "labeled paper trace",
    "initial values",
    "each relevant branch decision",
    "resulting writes",
    "retained values",
    "no grounded trace",
):
    if phrase not in workflow + "\n" + evidence:
        errors.append(f"conditional paper-trace guidance missing phrase: {phrase}")

for phrase in ("ladder walkthrough", "vendor-neutral", "branch joins", "unknown"):
    if phrase not in evals:
        errors.append(f"manual Ladder acceptance case missing phrase: {phrase}")

if errors:
    print("Foundation checks failed:")
    print("\n".join(f"- {error}" for error in errors))
    sys.exit(1)

print(f"Foundation checks passed ({len(REQUIRED)} required files, {len(all_markdown)} Markdown files).")
