#!/usr/bin/env python3
"""按文档实际适用内容校验 PLC 学习手册与专题文档。

用法：
  python3 scripts/validate_handbook.py <文档.md>
  python3 scripts/validate_handbook.py <文档.md> --final

退出码：0 通过，1 有问题。
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_plc_comments import PLC_LANGS, check_text, check_review, coverage_summary, fences, check_condition_ai, check_default_annotations
from markdown_fences import parse_fences, body_view, fence_diagnostics
from source_annotations import source_annotation
from block_layout import uses_block_layout, check_block_layout

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "references" / "template-index.md"
CHAPTERS = {
    "ch1": "## 一、工程与边界",
    "ch2": "## 二、执行框架",
    "ch3": "## 三、工艺主线",
    "ch4": "## 四、工位地图与段分类",
    "ch5": "## 五、模块详解",
    "ch6": "## 六、段间与工位间逻辑关系",
    "ch7": "## 七、关键 MFB/FB",
    "ch8": "## 八、异常、报警与恢复",
    "ch9": "## 九、未确认与证据",
    "ch10": "## 十、理解检验与审查",
}
CHAPTER_ORDER = tuple(CHAPTERS)
MODULE_PARTS = (
    "**1. 功能定位**",
    "**2. 推演示例**",
    "**3. 实现与逐句说明**",
    "**4. 与其他程序的交互**",
)
FORBIDDEN = ["其余略", "其余从略", "略过", "未展开", "同上", "见前文"]
COLLOQUIAL = ["就像", "好比", "打个比方", "说白了", "简单说就是"]
STATUSES = {"已讲", "待补资料", "共用模块引用", "受保护", "未讲解", "预留"}
UNFINISHED = {"待补资料", "受保护", "未讲解"}
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]")
TEMPLATE_RE = re.compile(r"\b([A-Z][A-Z0-9_-]*)@(\d+\.\d+)\b")
SAFE_NEGATION = re.compile(
    r"(?:不建议|不允许|不得|禁止|严禁|不可|不能|拒绝|避免|切勿|不要|不)"
    r"(?:[ \t，、]*(?:建议|允许|指导|做|进行|执行|实施|提供|通过|可以|应该|应当))?"
)
POSITIVE_TURN = re.compile(r"(?:但|但是|可是|然而|而是|转而|改为|所以|因此|随后|然后|可以|应该|应当|需要|建议)")
UNSAFE_ACTION = re.compile(
    r"修改\s*PLC\s*程序|强制(?:\s*(?:I/O|输出|输入|[XYM]\d+))?"
    r"|旁[路通]安全(?:回路)?|旁路互锁|下载|在线改参|设备试运行|产线试错", re.I)
DIRECTIVE = re.compile(r"请|建议|应当|应该|(?:^|[，,：:])应|需要|可以|务必|必须|先|然后|下一步|将|把|操作员应")
DESCRIPTION = re.compile(r"程序|源码|逻辑|指令|标志|现有|解释|描述|说明|分析|定义|记录")


def section(text: str, heading: str) -> str:
    match = re.search(rf"(?m)^{re.escape(heading)}(?:[^\n]*)$", body_view(text))
    if not match:
        return ""
    body = text[match.end():]
    nxt = re.search(r"(?m)^## ", body_view(body))
    return body[:nxt.start()] if nxt else body


def prose_for_safety(raw: str) -> str:
    """Keep prose and non-PLC examples; hide only copied PLC source fences."""
    lines = raw.splitlines()
    for block in parse_fences(raw):
        if block["lang"] not in PLC_LANGS:
            continue
        for index in range(block["line"] - 1, min(block["end_line"], len(lines))):
            lines[index] = ""
    return "\n".join(lines)


def chapter_id(heading: str, hbk: bool = False) -> str | None:
    # Explicit ch declarations opt into HBK numbering and its order diagnostics.
    if hbk and (match := re.match(r"##\s+([一二三四五六七八九十]+)、", heading)):
        return "ch" + str("一二三四五六七八九十".index(match.group(1)[0]) + 1)
    # Otherwise numbering belongs to each topical template.
    return next((key for key, title in CHAPTERS.items()
                 if heading == title or heading.startswith(title + " ")), None)


def emoji_errors(raw: str) -> list[str]:
    """Allow restrained decoration in headings/prompts, never in copied/data fields."""
    errors = []
    blocks = parse_fences(raw)
    for number, line in enumerate(raw.splitlines(), 1):
        opening = next((block for block in blocks if block["line"] == number), None)
        containing = next((block for block in blocks
                           if block["line"] < number <= block["end_line"]), None)
        if opening:
            if EMOJI_RE.search(line):
                errors.append(f"第 {number} 行围栏信息串内出现表情")
            continue
        if containing:
            if EMOJI_RE.search(line):
                errors.append(f"第 {number} 行代码块或表格字段内出现表情")
            continue
        if not EMOJI_RE.search(line):
            continue
        if line.lstrip().startswith("|"):
            errors.append(f"第 {number} 行代码块或表格字段内出现表情")
            continue
        inline_code = [m.span() for m in re.finditer(r"(`+).*?\1", line)]
        if any(EMOJI_RE.search(line[start:end]) for start, end in inline_code):
            errors.append(f"第 {number} 行行内代码中出现表情")
            continue
        # Only explicitly quoted policy fragments are exempt. Check all real
        # fields outside those spans before deciding whether prose may quote them.
        policy_quote = re.search(r"(?:引用|示例|反例|规则)", line)
        unquoted = re.sub(r'“[^”]*”|‘[^’]*’|"[^"\n]*"|\'[^\'\n]*\'', "", line) if policy_quote else line
        data_field = re.search(
            r"(?i)(?:工程名称|工程|项目名称|对象\s*ID|实例\s*ID|对象编号|\bID\b|证据等级|置信度)\s*[:：=]"
            r"|^\s*(?:>\s*)?[-*]?\s*`?[A-Za-z_][\w.-]*`?\s*[:：=]", unquoted
        ) or re.search(r"[A-Za-z_][A-Za-z_0-9.-]*[\U0001F300-\U0001FAFF\u2600-\u27BF]", unquoted)
        if data_field:
            errors.append(f"第 {number} 行元数据、标识符、证据字段或表格字段内出现表情")
            continue
        if policy_quote and not EMOJI_RE.search(unquoted):
            continue
        stripped = line.lstrip()
        if stripped.startswith(("#", ">", "- ", "* ")):
            continue
        errors.append(f"第 {number} 行普通正文不应以表情代替文字提示")
    return errors


def template_registry() -> dict[str, dict[str, object]]:
    if not INDEX.is_file():
        return {}
    text = INDEX.read_text(encoding="utf-8")
    block = text.split("## 模板注册表", 1)[-1].split("\n## ", 1)[0]
    lines = [line.strip() for line in block.splitlines() if line.strip().startswith("|")]
    registry: dict[str, dict[str, object]] = {}
    for line in lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 6:
            continue
        template_id, version, _, _, _, compatible = cells[:6]
        ids = set(re.findall(r"\b[A-Z][A-Z0-9_-]*\b", compatible))
        registry[template_id] = {"version": version, "compatible": ids}
    return registry


def check_template_combination(text: str, errors: list[str], warnings: list[str]) -> None:
    match = re.search(r"(?m)^>\s*模板组合：(.+)$", text)
    if not match:
        warnings.append("未记录模板 ID/版本（建议注明如 HBK@2.0 + FLOW@2.0）")
        return
    declared = TEMPLATE_RE.findall(match.group(1))
    if not declared:
        errors.append("模板组合格式错误：使用 ID@版本，如 HBK@2.0 + FLOW@2.0")
        return
    ids = [template_id for template_id, _ in declared]
    if len(ids) != len(set(ids)):
        errors.append("模板组合中 ID 重复")
    registry = template_registry()
    for template_id, version in declared:
        entry = registry.get(template_id)
        if not entry:
            errors.append(f"模板组合包含未知 ID：{template_id}")
        elif version != entry["version"]:
            historical = {'HBK': {'2.1','2.2'}, 'FB': {'2.1','2.2'}, 'ST': {'2.1','2.2'},
                          'STATE': {'2.1'}, 'INTERFACE': {'2.1'}, 'FLOW': {'2.1','2.2'}}
            if version in historical.get(template_id,set()):
                warnings.append(f"历史模板兼容检查：{template_id}@{version}；新稿使用{entry['version']}块级版式")
            else:
                errors.append(f"模板版本不兼容：{template_id}@{version}，当前为 {entry['version']}")
    for i, template_id in enumerate(ids):
        entry = registry.get(template_id)
        if not entry:
            continue
        compatible = entry["compatible"]
        for other in ids[i + 1:]:
            if other not in compatible:
                errors.append(f"模板组合不兼容：{template_id} + {other}")


def check_safety_boundary(text: str, errors: list[str]) -> None:
    for clause in re.split(r"[。；！？\n]", text):
        for match in UNSAFE_ACTION.finditer(clause):
            action = match.group()
            prefix, suffix = clause[:match.start()], clause[match.end():]
            negation = SAFE_NEGATION.search(prefix)
            if negation is not None and not POSITIVE_TURN.search(prefix[negation.end():]):
                continue
            # Downloading a document is an offline delivery action.
            if action == "下载" and re.match(r"(?:本|该|此)?(?:手册|文档|报告|PDF|附件)(?:供|以|用|[，。]|$)", suffix, re.I):
                continue
            # Requests to explain existing logic remain within the read-only task.
            explain = re.search(r"(?:解释|说明|分析|描述)(?:现有|当前)?$", prefix.strip())
            if explain and not re.search(r"(?:然后|随后|再)(?:请|应|去|进行)?(?:强制|下载|旁路)", suffix):
                continue
            directive = bool(DIRECTIVE.search(prefix))
            # '程序将强制标志写入诊断字' uses 将 as a narrative verb.
            if DESCRIPTION.search(prefix) and not re.search(r"请|建议|应当|应该|需要|可以|务必|必须|下一步|操作员应", prefix):
                directive = False
            imperative = True
            if DESCRIPTION.search(prefix) and not directive:
                imperative = False
            if re.match(r"指令|逻辑|完成(?:后|时)|失败(?:后|时)|行为|功能", suffix) and not directive:
                imperative = False
            # A table may state a hypothetical/current condition rather than
            # instruct the reader to force a device. An explicit directive wins.
            if (clause.lstrip().startswith("|") and "模式" in prefix
                    and not directive):
                imperative = False
            # Bare forcing descriptions such as '强制标志' are nouns, not actions.
            if action.startswith("强制") and re.match(r"标志|状态|位|信号", suffix) and not directive:
                imperative = False
            if imperative:
                errors.append(f"只读安全边界：不得建议或指导“{action}”")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("document", type=Path)
    ap.add_argument("--require-condition-ai", action="store_true", help="兼容旧调用：默认逐行注释已覆盖条件行")
    ap.add_argument("--original-source", action="store_true", help="仅当用户当次明确要求原样源码或归档时使用；不要求新增注释")
    ap.add_argument("--legacy-selective", action="store_true", help="仅复核历史选择性注释夹具；日常交付不得使用")
    ap.add_argument("--final", action="store_true", help="最终稿：拒绝未完成覆盖状态")
    ap.add_argument("--comment-review", type=Path, help="当前文档的逐块注释语义审查 JSON，最终稿必需")
    args = ap.parse_args(argv)
    if args.original_source and (args.legacy_selective or args.require_condition_ai):
        ap.error('原样源码模式与注释要求互斥')

    if not args.document.is_file():
        print(f"ERROR 找不到文件：{args.document}")
        return 1
    data = args.document.read_bytes()
    raw = data.decode("utf-8-sig")
    prose = body_view(raw)
    text = EMOJI_RE.sub("", prose)
    errors: list[str] = fence_diagnostics(raw)
    warnings: list[str] = []

    if "文档类型：handbook" not in text:
        errors.append("缺少元信息：文档类型：handbook")
    depth = re.search(r"深度：([^\n|]+)", text)
    if not depth:
        errors.append("缺少元信息：深度")
    elif len([d for d in ("结构深度", "流程深度", "代码深度") if d in depth.group(1)]) != 1:
        errors.append(f"深度必须是单一值，当前：{depth.group(1).strip()}")
    check_template_combination(text, errors, warnings)

    applicable = re.search(r"(?m)^>\s*适用章节：(.+)$", text)
    requested_chapters: set[str] = set()
    if applicable:
        requested_chapters = set(re.findall(r"ch\d+", applicable.group(1)))
        for chapter in requested_chapters:
            if chapter not in CHAPTERS:
                errors.append(f"适用章节 ID 未知：{chapter}")
            elif not re.search(rf"(?m)^{re.escape(CHAPTERS[chapter])}", text):
                errors.append(f"缺少章节：{CHAPTERS[chapter]}")
    else:
        warnings.append("未声明适用章节；仅校验文档中实际出现的章节与内容")

    # Only declared or present chapter structure is checked; topical documents may omit unrelated chapters.
    present_chapters: dict[str, str] = {}
    present_sequence: list[str] = []
    for heading in re.findall(r"(?m)^##\s+[^\n]+", text):
        chapter = chapter_id(heading, bool(requested_chapters))
        if chapter:
            present_sequence.append(chapter)
            if chapter in present_chapters:
                errors.append(f"章节重复：{chapter}")
            present_chapters[chapter] = heading

    chapter_rank = {chapter: index for index, chapter in enumerate(CHAPTER_ORDER)}
    if any(chapter_rank[cur] <= chapter_rank[prev] for prev, cur in zip(present_sequence, present_sequence[1:])):
        errors.append("章节顺序错误：必须遵循规范顺序，允许省略章节但不允许倒序或重复")
    if applicable:
        declared_sequence = re.findall(r"ch\d+", applicable.group(1))
        if declared_sequence != list(dict.fromkeys(declared_sequence)):
            errors.append("适用章节顺序错误：章节 ID 不得重复")
        if [ch for ch in present_sequence if ch in requested_chapters] != present_sequence:
            errors.append("章节顺序错误：正文必须是适用章节的有序子集")

    for chapter, base_heading in CHAPTERS.items():
        if chapter in present_chapters:
            body = section(text, base_heading)
            if not body.strip():
                errors.append(f"章节为空：{base_heading}")
        elif applicable and chapter in re.findall(r"ch\d+", applicable.group(1)):
            # The missing section was already reported above.
            continue
    if applicable:
        for chapter in sorted(set(present_chapters) - requested_chapters):
            errors.append(f"章节超出适用章节范围：{chapter}")

    comment_report = check_text(raw, require_units=not args.original_source)
    errors.extend(comment_report["errors"])
    if not args.original_source and not args.legacy_selective:
        # 默认交付要求逐行业务尾注，包括结构闭合行；空白与纯注释行不补。
        errors.extend(check_default_annotations(raw))
    if args.require_condition_ai:
        errors.extend(error for error in check_condition_ai(raw) if error not in errors)
    errors.extend(check_review(raw, comment_report["blocks"], args.comment_review, args.final, hashlib.sha256(data).hexdigest()))
    code_blocks = [block for block in fences(raw) if block["lang"] in PLC_LANGS]
    for block in code_blocks:
        if source_annotation(raw, block) is None:
            errors.append(f"第 {block['line']} 行没有任何 <!-- src: 起-止 --> 有效标记，代码块无法对账")

    # Directory links are required for multi-section documents; all links that exist must resolve uniquely.
    h2_count = len(re.findall(r"(?m)^## ", text))
    toc = section(text, "## 目录")
    if h2_count >= 3 and not toc:
        errors.append("缺少目录（## 目录）")
    ids_list = re.findall(r'<a id="([^\"]+)"', prose)
    ids = set(ids_list)
    for anchor, count in Counter(ids_list).items():
        if count > 1:
            errors.append(f"锚点重复：{anchor}")
    for target in re.findall(r"\]\(#([A-Za-z0-9_-]+)\)", prose):
        if target not in ids:
            errors.append(f"交叉引用失效：# {target} 没有对应锚点")
    for match in re.finditer(r"(?m)^####\s+\[(M\d{2})\]\(#([A-Za-z0-9_-]+)\)", prose):
        if match.group(1).lower() == match.group(2).lower():
            errors.append("模块标题不应把编号链接到自身锚点；在标题前放置锚点，目录中设置跳转")
    module_jump = toc + section(prose, "### 模块跳转")
    for match in re.finditer(r"(?m)^####\s+((?:M|W)\d{2})\s+", prose):
        module_id = match.group(1).lower()
        prefix = raw[:match.start()].rstrip().splitlines()[-1:]
        if not prefix or prefix[0].strip() != f'<a id="{module_id}"></a>':
            errors.append(f"模块标题缺少匹配锚点：{module_id}")
        if f"](#{module_id})" not in module_jump:
            errors.append(f"模块 {module_id.upper()} 未加入目录或模块跳转表")
    for chapter, heading in present_chapters.items():
        prefix = raw[:prose.find(heading)].rstrip().splitlines()[-1:]
        if not prefix or prefix[0].strip() != f'<a id="{chapter}"></a>':
            errors.append(f"章节标题缺少匹配锚点：{chapter}")
        if toc and f"](#{chapter})" not in toc:
            errors.append(f"章节未加入目录：{chapter}")

    craft = section(text, CHAPTERS["ch3"])
    craft_rows = [ln for ln in craft.splitlines() if ln.strip().startswith("|") and "---" not in ln]
    mermaid_text = "\n".join(b["text"] for b in parse_fences(raw) if b["lang"] == "mermaid")
    if "stateDiagram-v2" in mermaid_text and craft and len(craft_rows) <= 1:
        errors.append("有状态机图但工艺主线没有步转移表")
    elif craft and "stateDiagram-v2" not in mermaid_text and len(craft_rows) > 3:
        warnings.append("工艺主线有多个步但缺少状态机图（建议加 stateDiagram-v2）")

    for alarm_heading in re.findall(r"(?m)^##\s+[^\n]+", text):
        if "异常" not in alarm_heading and "报警" not in alarm_heading:
            continue
        alarm = section(text, alarm_heading)
        alarm_head = next((ln for ln in alarm.splitlines() if ln.strip().startswith("|")), "")
        # FB execution-state tables belong to STATE, even when the topic also
        # discusses exceptions. Actual alarm matrices still use the HBK fields.
        state_table = "当前状态" in alarm_head and "报警" not in alarm_head
        if alarm_head and not (state_table and chapter_id(alarm_heading) != "ch8"):
            for col in ("报警码", "复位方式", "恢复起点"):
                if col not in alarm_head:
                    errors.append(f"报警矩阵缺少“{col}”列")

    errors.extend(emoji_errors(raw))

    for phrase in FORBIDDEN:
        if phrase in text:
            errors.append(f"出现禁止省略用语：{phrase}")
    # Safety guidance is a prose constraint; copied PLC fences may contain
    # historical words such as "强制屏蔽" that are data, not instructions.
    check_safety_boundary(EMOJI_RE.sub("", prose_for_safety(raw)), errors)

    coverage = section(text, CHAPTERS["ch4"])
    detail = section(raw, CHAPTERS["ch5"])
    if detail and code_blocks and "源码块覆盖清单" not in detail:
        errors.append("模块详解缺少源码块覆盖清单（编号 / 对象 ID / 范围 / 状态）")
    if coverage:
        rows = [ln for ln in coverage.splitlines() if ln.strip().startswith("|") and "---" not in ln]
        if "源码块覆盖清单" in coverage and len(rows) <= 1:
            errors.append("源码块覆盖清单为空")

    # Coverage claims use stable module IDs, not row order or a guessed count.
    from block_layout import modules as block_modules
    module_bodies = ({mid:body for mid,body,_,_ in block_modules(raw)} if uses_block_layout(raw) else
                     {m[1]:m[2] for m in re.finditer(r'(?ms)^####\s+(M\d{2})\s+([^\n]+\n.*?)(?=^####\s+M\d{2}\s+|\Z)', detail)})
    # Visit every coverage table in chapters 4/5; anchors must not end scanning.
    header = []
    for line in (coverage + '\n' + body_view(detail)).splitlines():
        if not line.strip().startswith('|'):
            header = []
            continue
        cells = [cell.strip().strip('`') for cell in line.strip().strip('|').split('|')]
        if '编号' in cells and any('状态' in cell for cell in cells):
            header = cells
            continue
        if '已讲' not in cells:
            continue
        # Old unlabeled contiguous rows remain checked, while an explicit header
        # selects only source/module inventories, not interface or relation tables.
        if header and ('编号' not in header or not any('对象' in c or '模块' in c for c in header)):
            continue
        id_text = ' '.join(cells[:2])
        modules = set(re.findall(r'\b(?:M\d{2}|B\d{1,2})\b', id_text))
        for prefix, first, last in re.findall(r'\b([MB])(\d{1,2})\s*[–—~～-]\s*\1?(\d{1,2})', id_text):
            if int(first) > int(last):
                errors.append('已讲模块区间逆序：' + id_text)
            else:
                modules.update(f'{prefix}{n:02d}' if prefix == 'M' else f'{prefix}{n}'
                               for n in range(int(first), int(last) + 1))
        if not modules:
            errors.append('已讲覆盖行须登记模块 ID（Mxx 或 Bx）')
        for module in sorted(modules):
            if module not in module_bodies:
                errors.append(f'已讲模块缺少正文：{module}')
            elif not any(b['lang'] in PLC_LANGS for b in parse_fences(module_bodies[module])):
                errors.append(f'已讲模块缺少可读源码：{module}；仅摘要应登记待补资料')

    unfinished: set[str] = set()
    in_scope_unfinished: set[str] = set()
    current_heading = ""
    for line in text.splitlines():
        if line.startswith("## "):
            current_heading = line[3:].strip()
        field = re.search(r"(?:状态|本体可见性)[：:]\s*(受保护|未讲解|待补资料|部分|未提供)", line)
        hit = {field[1]} if field else set()
        if re.search(r"本次交付[：:]\s*未完成", line):
            hit.add("本次交付未完成")
        uncovered = re.search(r"(?:尚未覆盖|未覆盖)[：:]\s*([^|]+)", line)
        if uncovered and uncovered[1].strip().strip("。；; ") not in {"无", "不适用", "无（本次范围）"}:
            hit.add("未覆盖")
        if line.strip().startswith("|"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            hit |= set(cells) & UNFINISHED
        unfinished |= hit
        if current_heading != "范围外缺口":
            in_scope_unfinished |= hit
    local = bool(re.search(r"(?m)^>\s*交付范围：局部\s*$", text))
    if args.final and local:
        required = (r"本次覆盖：\S[^\n]*", r"本次交付：完成", r"项目源码覆盖：(?:部分覆盖|无法对账)")
        if not all(re.search(r"(?m)^>\s*" + item + r"\s*$", text) for item in required):
            errors.append("局部成品须明确本次覆盖、本次交付：完成及项目源码覆盖：部分覆盖/无法对账")
        if in_scope_unfinished:
            errors.append("最终交付仍有未完成覆盖状态：" + "、".join(sorted(in_scope_unfinished)))
        if not section(text, "## 范围外缺口").strip():
            errors.append("局部成品须在 ## 范围外缺口 登记未覆盖对象、原因和影响")
    elif args.final and (unfinished or re.search(r"项目源码覆盖：(?:部分覆盖|无法对账)", text)):
        errors.append("最终交付仍有未完成覆盖状态：" + "、".join(sorted(unfinished)))

    block_layout = uses_block_layout(raw)
    if block_layout:
        errors.extend(check_block_layout(raw, mode="handbook"))
    # Historical four-part documents retain their original checks, never imposed on new block prose.
    starts = [] if block_layout else [m.end() for m in re.finditer(r"(?m)^####\s+(?=M\d{2}\s)", body_view(detail))]
    module_parts = [detail[start:end] for start, end in zip(starts, starts[1:] + [len(detail)])]
    for part in module_parts:
        code_lines = sum(len([ln for ln in b["text"].splitlines() if ln.strip()]) for b in fences(part) if b["lang"] in PLC_LANGS)
        raw_part = part
        part = body_view(part)
        title = part.splitlines()[0].strip()[:24] if part.splitlines() else "?"
        positions = [part.find(label) for label in MODULE_PARTS]
        missing_parts = [label for label, pos in zip(MODULE_PARTS, positions) if pos < 0]
        if missing_parts:
            errors.append(f"模块四部分不完整：{title} 缺少" + "、".join(missing_parts))
        if any(part.count(label) != 1 for label in MODULE_PARTS):
            repeated = [label for label in MODULE_PARTS if part.count(label) != 1]
            errors.append(f"模块四部分数量错误：{title} 的" + "、".join(repeated) + "必须各出现一次")
        if all(pos >= 0 for pos in positions) and positions != sorted(positions):
            errors.append(f"模块四部分顺序错误：{title} 必须按 1→2→3→4 排列")
        if re.search(r"(?m)^#{1,6}\s+[1-4]\.\s+", part):
            errors.append(f"模块四部分必须使用普通粗体小标题：{title}")
        if "职责" not in part.split(MODULE_PARTS[0], 1)[0]:
            errors.append(f"模块「{title}」缺少职责说明")
        if not re.search(r"(?m)^\d+\. \*\*[^*]+：\*\*", part.split(MODULE_PARTS[0], 1)[0]):
            errors.append(f"模块「{title}」缺少编号条目式详解")
        if not code_lines:
            continue
        code_block = next((block for block in fences(raw_part) if block["lang"] in PLC_LANGS), None)
        example_pos = raw_part.find(MODULE_PARTS[1])
        scenario_table_pos = raw_part.find("| 场景 |")
        implementation_pos = raw_part.find(MODULE_PARTS[2])
        raw_lines = raw_part.splitlines(keepends=True)
        code_pos = (sum(len(line) for line in raw_lines[:code_block["line"] - 1])
                    if code_block else -1)
        if not (0 <= example_pos < scenario_table_pos < implementation_pos < code_pos):
            errors.append(f"模块「{title}」示例必须位于 PLC 源码之前")
        example = (body_view(raw_part[example_pos:implementation_pos])
                   if example_pos >= 0 and implementation_pos > example_pos else "")
        has_initial = bool(re.search(r"(?:初始状态|开始时|起始时)[^|]*`[^`]+=[^`]+`", example))
        has_sequence = bool(re.search(r"依次|第\s*\d+\s*(?:次)?(?:扫描|周期)|连续\s*\d+\s*(?:扫描|周期)|变为", example))
        has_outcome = bool(re.search(r"结果由|结果为|写入|保持|推进至|置位|输出为", example))
        if not (has_initial and has_sequence and has_outcome):
            errors.append(f"模块「{title}」示例须包含初始状态、输入序列和预期结果")
        explanation = re.search(r'(?ms)^\*\*逐句看\*\*\s*\n(.*?)(?=^\*\*[^\n]+\*\*\s*$|\Z)', part)
        items = re.findall(r'(?m)^- `([^`]+)`[：:]\s*(.+)$', explanation[1] if explanation else '')
        normalize = lambda value: re.sub(r'\s+|;', '', re.sub(r'\bTHEN\s*$', '', value, flags=re.I)).casefold()
        keys = [normalize(key) for key, prose in items if prose.strip()]
        missing = []
        for block in check_text(raw_part)['blocks']:
            for unit in block['required_units']:
                source = normalize(unit['source'])
                if source not in keys:
                    missing.append(unit['source'].strip())
        if not items or missing:
            errors.append(f"段「{title}」逐句说明缺失或未覆盖执行单元：" + '、'.join(missing))
        if "逐句" in part:
            analogy = part.find("形象理解")
            line_by_line = part.find("**逐句看**")
            if analogy >= 0 and analogy < line_by_line:
                errors.append(f"段「{title}」形象类比必须放在逐句说明之后")
    for bad in ("框架", "B0b"):
        if re.search(rf"(?m)^#+\s*{bad}", text):
            errors.append(f"出现无语义标题：{bad}（改用模块名称）")
    for phrase in COLLOQUIAL:
        if phrase in text:
            warnings.append(f"出现口语化表述：{phrase}（技术文档建议改为术语描述）")

    rel = section(text, CHAPTERS["ch6"])
    rel_rows = [ln for ln in rel.splitlines() if ln.strip().startswith("|") and "---" not in ln]
    if rel and len(rel_rows) <= 1:
        errors.append("段间逻辑关系表为空")
    elif rel and not any(kind in rel for kind in ("数据", "顺序", "状态", "互锁", "异常")):
        warnings.append("段间关系表未体现依赖类型，建议标注数据/顺序/状态/互锁/异常")

    print(f"手册: {args.document.name}  适用章节: {len(present_chapters)} 项  源码块: {len(code_blocks)}")
    for block in comment_report["blocks"]:
        print(coverage_summary(block))
    if code_blocks:
        print("语义审查：" + ("已核验作者逐块记录（非机器语义证明）" if args.comment_review and not errors else "待完成或有错误；不得称注释质量全部合格"))
    for warning in warnings:
        print(f"WARN {warning}")
    for error in errors:
        print(f"ERROR {error}")
    if errors:
        print(f"\n失败：{len(errors)} 个错误，{len(warnings)} 个警告")
        return 1
    print(f"\n通过：0 个错误，{len(warnings)} 个警告")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
