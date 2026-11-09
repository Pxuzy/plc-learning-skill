#!/usr/bin/env python3
"""校验模板索引 ID、版本、文件、路由和组合关系。"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_HEADING = "## 模板注册表"
ROUTES_HEADING = "## 路由规则"
REGISTRY_COLUMNS = ["ID", "版本", "文件", "类型", "触发条件", "可组合模板"]
ROUTE_COLUMNS = ["ID", "用户请求 / 资料触发", "输出组合", "选择边界"]


def table_rows(text: str, heading: str) -> tuple[list[str], list[list[str]]]:
    if heading not in text:
        return [], []
    section = text.split(heading, 1)[1].split("\n## ", 1)[0]
    lines = [line.strip() for line in section.splitlines() if line.strip().startswith("|")]
    if not lines:
        return [], []
    split = lambda line: [cell.strip() for cell in line.strip("|").split("|")]
    headers = split(lines[0])
    rows = [split(line) for line in lines[2:] if not re.fullmatch(r"\|?[\s:|-]+\|?", line)]
    return headers, rows


def ids_from(value: str) -> set[str]:
    return set(re.findall(r"\b[A-Z][A-Z0-9_-]*\b", value)) - {"NONE"}


def validate_text(text: str, root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    headers, rows = table_rows(text, REGISTRY_HEADING)
    if headers != REGISTRY_COLUMNS:
        errors.append("模板注册表列不符合契约：" + " / ".join(REGISTRY_COLUMNS))
        return errors

    registry: dict[str, dict[str, str]] = {}
    for row in rows:
        if len(row) != len(REGISTRY_COLUMNS):
            errors.append(f"模板注册表列数错误：{' | '.join(row)}")
            continue
        template_id, version, path, kind, trigger, compatible = row
        if not re.fullmatch(r"[A-Z][A-Z0-9_-]*", template_id):
            errors.append(f"模板 ID 格式错误：{template_id}")
            continue
        if template_id in registry:
            errors.append(f"模板 ID 重复：{template_id}")
            continue
        if not re.fullmatch(r"\d+\.\d+", version):
            errors.append(f"模板版本格式错误：{template_id}@{version}")
        file_match = re.fullmatch(r"`(references/[^`]+\.md)`", path)
        if not file_match:
            errors.append(f"模板路径格式错误：{template_id}: {path}")
        elif not (root / file_match.group(1)).is_file():
            errors.append(f"模板文件不存在：{file_match.group(1)}")
        if not kind or not trigger:
            errors.append(f"模板用途字段为空：{template_id}")
        registry[template_id] = {"compatible": compatible, "version": version, "path": file_match.group(1) if file_match else ""}
        if file_match and (root / file_match.group(1)).is_file():
            declaration = (root / file_match.group(1)).read_text(encoding="utf-8")
            if f"<!-- template-id: {template_id}@{version} -->" not in declaration:
                errors.append(f"模板文件自声明不匹配：{template_id}@{version} -> {file_match.group(1)}")

    if not registry:
        errors.append("模板注册表为空")
        return errors
    if "HBK" not in registry:
        errors.append("缺少共享基底 HBK")

    compatible_ids = {key: ids_from(value["compatible"]) for key, value in registry.items()}
    for template_id, compatible in compatible_ids.items():
        for other in compatible:
            if other == template_id or other not in registry:
                errors.append(f"模板组合引用无效：{template_id} + {other}")
            elif template_id not in compatible_ids.get(other, set()):
                errors.append(f"组合关系不对称：{template_id} + {other}")
        if template_id not in {"HBK", "OVR", "MAP", "BOOKSET"} and "HBK" not in compatible:
            errors.append(f"扩展模板必须可组合共享基底 HBK：{template_id}")

    route_headers, route_rows = table_rows(text, ROUTES_HEADING)
    if route_headers != ROUTE_COLUMNS:
        errors.append("路由表列不符合契约：" + " / ".join(ROUTE_COLUMNS))
        routed: set[str] = set()
    else:
        routed = set()
        for row in route_rows:
            if len(row) != len(ROUTE_COLUMNS) or not all(row):
                errors.append("路由表列数错误或字段为空：" + " | ".join(row))
                continue
            route_id = row[0]
            if route_id in routed:
                errors.append(f"路由 ID 重复：{route_id}")
            routed.add(route_id)
        for template_id in registry:
            if template_id not in routed:
                errors.append(f"模板未登记路由：{template_id}")
        for template_id in routed - registry.keys():
            errors.append(f"路由引用未知模板：{template_id}")

    for heading in ("## 资料不足与降级", "## 版本策略"):
        if heading not in text:
            errors.append(f"缺少索引规则章节：{heading}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", nargs="?", type=Path, default=ROOT / "references" / "template-index.md")
    args = parser.parse_args(argv)
    if not args.index.is_file():
        print(f"ERROR 找不到索引：{args.index}")
        return 1
    text = args.index.read_text(encoding="utf-8")
    errors = validate_text(text, ROOT)
    if errors:
        for error in errors:
            print(f"ERROR {error}")
        print(f"\n失败：{len(errors)} 个错误")
        return 1
    print(f"模板索引通过：{args.index.name}，{len(table_rows(text, REGISTRY_HEADING)[1])} 个模板均有唯一 ID、版本、文件与路由")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
