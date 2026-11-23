#!/usr/bin/env python3
"""Read one selected FunctionBlock's declaration and/or Structured Text body."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import tempfile
import subprocess
import os
import re
import stat
import sys
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from uuid import UUID
from xml.etree import ElementTree as ET

if __package__:
    from .inspect_smc2_archive import (
        DEFAULT_MAX_MEMBER_BYTES,
        DEFAULT_MAX_MEMBERS,
        DEFAULT_MAX_TOTAL_BYTES,
        decode_xml,
        safe_member_name,
    )
else:
    from inspect_smc2_archive import (
        DEFAULT_MAX_MEMBER_BYTES,
        DEFAULT_MAX_MEMBERS,
        DEFAULT_MAX_TOTAL_BYTES,
        decode_xml,
        safe_member_name,
    )

OEM_LIMIT = 8 * 1024 * 1024
ROLES = {"variables": ("Variables", "SourceHolder"), "body": ("PouBody", "PouBodySourceHolder")}


class LocateError(ValueError):
    pass


def canonical_guid(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(UUID(value.strip("{}"))).lower()
    except (ValueError, AttributeError):
        return None


def _check_tree(root: ET.Element) -> str:
    if root.tag.startswith("{"):
        return root.tag[1:].split("}", 1)[0]
    return ""


def _tag(element: ET.Element, namespace: str, name: str) -> bool:
    return element.tag == (f"{{{namespace}}}{name}" if namespace else name)


def _xml(raw: bytes, label: str) -> ET.Element:
    try:
        text = decode_xml(raw)
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.I):
        raise LocateError(f"xml_rejected_dtd: {label}")
    try:
        return ET.fromstring(raw)
    except (ET.ParseError, ValueError, LookupError) as exc:
        raise LocateError(f"invalid_xml: {label}: {exc}") from None


def _entity_children(parent: ET.Element, namespace: str) -> list[ET.Element]:
    result = []
    for container in parent:
        if not _tag(container, namespace, "ChildEntities"):
            continue
        result.extend(child for child in container if _tag(child, namespace, "Entity"))
    return result


def _collect_entities(root: ET.Element, namespace: str) -> tuple[list[ET.Element], str | None]:
    entities: list[ET.Element] = []
    visited: set[int] = set()

    direct = [child for child in root if _tag(child, namespace, "Entity")]
    contained = _entity_children(root, namespace)
    if direct and contained:
        raise LocateError("unsupported_layout: mixed root Entity and ChildEntities layouts")
    roots = direct or contained
    layout = "root_entity" if direct else "root_child_entities" if contained else None

    def visit(entity: ET.Element) -> None:
        if id(entity) in visited:
            return
        visited.add(id(entity))
        entities.append(entity)
        for child in _entity_children(entity, namespace):
            visit(child)

    for entity in roots:
        visit(entity)

    undiscovered = [element for element in root.iter()
                    if element is not root and _tag(element, namespace, "Entity")
                    and id(element) not in visited]
    if undiscovered:
        raise LocateError("unsupported_layout: Entity outside supported root/ChildEntities tree")

    return entities, layout


def _parse_oem(raw: bytes) -> tuple[str, dict]:
    root = _xml(raw, "OEM")
    if not _tag(root, _check_tree(root), "sysmac") or root.attrib.get("schemaVersion") != "1":
        raise LocateError("unsupported_layout: expected sysmac schemaVersion=1")
    namespace = _check_tree(root)
    entities, layout = _collect_entities(root, namespace)
    if not layout:
        raise LocateError("unsupported_layout: no same-namespace root Entity tree")
    ids: dict[str, list[ET.Element]] = {}
    for entity in entities:
        identifier = entity.get("id")
        if identifier:
            ids.setdefault(canonical_guid(identifier) or "raw:" + identifier, []).append(entity)
    duplicates = sorted(key for key, values in ids.items() if len(values) > 1)
    if duplicates:
        raise LocateError("duplicate_id: " + ", ".join(duplicates[:10]))
    return namespace, {"entities": entities, "ids": ids}


def _path_for(entity: ET.Element, entities: list[ET.Element], namespace: str) -> str:
    parent_by_child: dict[int, ET.Element] = {}
    for parent in entities:
        for child in _entity_children(parent, namespace):
            parent_by_child[id(child)] = parent
    parts = []
    cursor = entity
    while cursor is not None:
        parts.append(cursor.get("name", "[unnamed]"))
        cursor = parent_by_child.get(id(cursor))
    return "/".join(reversed(parts))


def _definitions(name: str, entities: list[ET.Element]) -> tuple[list[ET.Element], list[ET.Element]]:
    named = [entity for entity in entities if entity.get("name") == name]
    definitions = [entity for entity in named
                   if entity.get("type") == "FunctionBlock" and
                   entity.get("subtype", "").lower() in {"structuredtext", "st"}]
    return definitions, named


def _source_ref(role: ET.Element, holder_type: str, namespace: str) -> tuple[str | None, dict]:
    child_entities = _entity_children(role, namespace)
    holders = [child for child in child_entities
               if child.get("type") == holder_type]
    # The interface/library holder is a sibling, not a declaration source.
    known_holder_types = {value[1] for value in ROLES.values()} | {"PouIFLibraryHolder"}
    other_known_holders = [child for child in child_entities
                           if child.get("type") in known_holder_types
                           and child not in holders]
    other_holders = [child for child in child_entities
                     if (child.get("type") == holder_type or child.get("name") == holder_type or
                         "holder" in (child.get("type", "") + child.get("name", "")).casefold())
                     and child not in holders and child not in other_known_holders]
    paths = []
    for candidate in [role, *holders]:
        for key in ("SourcePath", "FilePath", "URI"):
            value = candidate.get(key)
            if value:
                paths.append({"path": value, "attribute": key,
                              "holder_id": candidate.get("id") if candidate is not role else None})
    unsafe = [item["path"] for item in paths if not safe_member_name(item["path"])]
    other_holder_evidence = [{"id": item.get("id"), "name": item.get("name"),
                              "type": item.get("type"), "references": {
                                  key: item.get(key) for key in ("SourcePath", "FilePath", "URI")
                                  if item.get(key)}} for item in other_holders]
    return (paths[0]["path"] if len(paths) == 1 and not unsafe else None), {
        "status": "unsafe_explicit_path" if unsafe else
                  "duplicate_holder_reference" if len(holders) > 1 else
                  "unsupported_holder_layout" if other_holders else
                  "explicit_path" if len(paths) == 1 else
                  "other_holder_only" if other_known_holders and not holders else
                  "no_explicit_path" if not paths else "ambiguous_explicit_path",
        "paths": paths,
        "unsafe_paths": unsafe,
        "other_holders": other_holder_evidence,
        "other_known_holders": [{"id": item.get("id"), "name": item.get("name"),
                                  "type": item.get("type")} for item in other_known_holders],
        "holders": [{"id": item.get("id"), "name": item.get("name"), "type": item.get("type")}
                    for item in holders],
    }


def _valid_slwd_declarations(text: str) -> bool:
    """Recognize bounded declaration shapes without rewriting their raw text.

    The record form is a synthetic-tested structural check, not a complete
    Sysmac SLWD grammar. Unknown keyed extension fields remain untouched.
    """
    lines = text.splitlines()
    if not lines or lines[0] != "[SLWD version=1.0]" or "\x00" in text:
        return False
    if not any(line.startswith(("+GN=", "++D=")) for line in lines[1:]):
        starts = re.findall(r"(?m)^\s*VAR(?:_INPUT|_OUTPUT|_IN_OUT)?\s*$", text)
        ends = re.findall(r"(?m)^\s*END_VAR\s*$", text)
        return bool(starts) and len(starts) == len(ends)

    current_group = None
    declarations = 0
    for line in lines[1:]:
        if not line.strip():
            continue
        fields = {}
        for token in line.split("\t"):
            key, separator, value = token.partition("=")
            if (not separator or not re.fullmatch(r"\+{0,2}[A-Za-z_][A-Za-z0-9_]*", key)
                    or key in fields):
                return False
            fields[key] = value
        first = next(iter(fields))
        if first.startswith("_"):
            if current_group is not None or declarations:
                return False
            if "_EN" in fields and fields["_EN"] != "Variables":
                return False
        elif first == "+GN":
            current_group = fields["+GN"]
            if not current_group.strip():
                return False
        elif first == "++D":
            group = fields.get("G", current_group)
            if (not fields["++D"].strip() or not fields.get("N", "").strip()
                    or not group or not group.strip()):
                return False
            declarations += 1
        else:
            return False
    return declarations > 0


def _branch(role: ET.Element | None, role_name: str, namespace: str,
            member_index: dict[str, list], guid_index: dict[str, list],
            read_member, include_source: bool) -> dict:
    if role is None:
        return {"status": "role_missing"}
    identifier = role.get("id")
    guid = canonical_guid(identifier)
    result = {"role_id": guid or identifier, "status": "unresolved_reference"}
    if not guid:
        result["status"] = "invalid_role_guid"
        return result
    matches = guid_index.get(guid, [])
    path, holder_evidence = _source_ref(role, ROLES[role_name][1], namespace)
    result["holder_evidence"] = holder_evidence
    if holder_evidence["status"] in {
        "ambiguous_explicit_path", "duplicate_holder_reference", "unsupported_holder_layout"
    }:
        result["status"] = "reference_conflict"
        result["explicit_paths"] = [item["path"] for item in holder_evidence["paths"]]
        return result
    if holder_evidence["status"] == "unsafe_explicit_path":
        result["status"] = "unsafe_reference"
        return result
    if len(matches) > 1:
        result["status"] = "ambiguous_member"
        return result
    direct = matches[0] if matches else None
    explicit = None
    if path and holder_evidence["status"] == "explicit_path":
        explicit_candidates = member_index.get(str(PurePosixPath(path)).casefold(), [])
        if len(explicit_candidates) != 1:
            result["status"] = "reference_conflict" if direct else "unresolved_reference"
            result["explicit_path"] = path
            return result
        explicit = explicit_candidates[0]
    if direct and explicit and direct["path"].casefold() != explicit["path"].casefold():
        result["status"] = "reference_conflict"
        result["direct_member"] = direct["path"]
        result["explicit_member"] = explicit["path"]
        return result
    selected = explicit or direct
    if selected is None:
        if holder_evidence["status"] in {
            "ambiguous_explicit_path", "unsupported_holder_layout", "other_holder_only"
        }:
            result["status"] = "unresolved_reference"
        else:
            result["status"] = "missing_member"
        return result
    result.update({"member_path": selected["path"],
                   "mapping_basis": "holder_source_path" if explicit else "role_guid_basename",
                   "content_fingerprint_is_not_ownership_evidence": True})
    try:
        raw = read_member(selected)
        if role_name == "variables":
            text = raw.decode("utf-8-sig")
            if not _valid_slwd_declarations(text):
                result["status"] = "invalid_content"
                return result
            source, semantics = text, "complete SLWD; readable declaration payload, grammar not independently confirmed"
        else:
            if len(raw) > OEM_LIMIT:
                result["status"] = "invalid_content"
                return result
            root = _xml(raw, selected["path"])
            source_namespace = _check_tree(root)
            texts = [child for child in list(root) if _tag(child, source_namespace, "Text")]
            if (not _tag(root, source_namespace, "StructuredTextModel") or len(texts) != 1 or
                    len(list(root)) != 1 or list(texts[0])):
                result["status"] = "invalid_content"
                return result
            source, semantics = texts[0].text or "", "XML Text node decoded logical text; XML line endings are normalized"
            if not source.strip():
                result["status"] = "invalid_content"
                return result
        result["status"] = "complete"
        result["content_coordinate"] = "whole member" if role_name == "variables" else "StructuredTextModel/Text"
        result["source_semantics"] = semantics
        if include_source:
            result["source"] = source
    except (UnicodeDecodeError, LocateError, OSError, zipfile.BadZipFile, RuntimeError) as exc:
        result["status"] = "invalid_content"
        result["content_error"] = str(exc)
    return result


class _Reader:
    def __init__(self, path: Path, *, max_members: int, max_total_bytes: int, max_member_bytes: int):
        self.path = path
        self.archive = None
        self.members: dict[str, list] = {}
        if path.is_dir():
            self._directory(max_members, max_total_bytes, max_member_bytes)
        else:
            if not zipfile.is_zipfile(path):
                raise LocateError("invalid_input: expected .smc2 ZIP or directory")
            self.archive = zipfile.ZipFile(path)
            infos = [item for item in self.archive.infolist() if not item.is_dir()]
            self._validate_names((info.filename for info in infos))
            for info in infos:
                mode = info.external_attr >> 16
                file_type = stat.S_IFMT(mode)
                if info.create_system == 3 and file_type and file_type != stat.S_IFREG:
                    raise LocateError("unsafe_path: non-regular ZIP member " + info.filename)
            _check_budgets(infos, max_members, max_total_bytes, max_member_bytes)
            for info in infos:
                self.members.setdefault(info.filename.lower(), []).append({"path": info.filename, "info": info})

    def _validate_names(self, names):
        seen = set()
        for name in names:
            if not safe_member_name(name):
                raise LocateError("unsafe_path: " + name)
            norm = str(PurePosixPath(name)).casefold()
            if norm in seen:
                raise LocateError("duplicate_member: " + norm)
            seen.add(norm)

    def _directory(self, max_members, max_total_bytes, max_member_bytes):
        root = self.path.resolve(strict=True)
        entries = []
        for current, dirs, files in os.walk(root, followlinks=False):
            current_path = Path(current)
            for name in list(dirs):
                item = current_path / name
                if item.is_symlink():
                    raise LocateError("unsafe_path: symbolic link " + str(item.relative_to(root)))
                if not item.is_dir():
                    raise LocateError("unsafe_path: non-directory " + str(item.relative_to(root)))
            for name in files:
                item = current_path / name
                if item.is_symlink() or not item.is_file():
                    raise LocateError("unsafe_path: non-regular file " + str(item.relative_to(root)))
                info = item.stat(follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink > 1:
                    raise LocateError("unsafe_path: non-regular or linked file " + str(item.relative_to(root)))
                rel = item.relative_to(root).as_posix()
                entries.append({"path": rel, "file": item, "size": info.st_size})
        self._validate_names(item["path"] for item in entries)
        _check_budgets(entries, max_members, max_total_bytes, max_member_bytes)
        self.members = {}
        for entry in entries:
            self.members.setdefault(entry["path"].lower(), []).append(entry)

    def read(self, member):
        if self.archive:
            with self.archive.open(member["info"]) as stream:
                data = stream.read(member["info"].file_size + 1)
        else:
            path = member["file"]
            if path.is_symlink() or not path.is_file():
                raise LocateError("unsafe_path: changed member " + member["path"])
            with path.open("rb") as stream:
                data = stream.read(member["size"] + 1)
        expected_size = member["size"] if "size" in member else member["info"].file_size
        if len(data) > expected_size:
            raise LocateError("read_budget_exceeded: " + member["path"])
        return data

    def close(self):
        if self.archive:
            self.archive.close()


def _check_budgets(items, max_members, max_total_bytes, max_member_bytes):
    if len(items) > max_members:
        raise LocateError(f"member_budget_exceeded: {len(items)} > {max_members}")
    sizes = [item.file_size if isinstance(item, zipfile.ZipInfo) else
             item["size"] if "size" in item else item["info"].file_size for item in items]
    if any(size > max_member_bytes for size in sizes):
        raise LocateError(f"member_size_budget_exceeded: max {max_member_bytes}")
    if sum(sizes) > max_total_bytes:
        raise LocateError(f"total_size_budget_exceeded: {sum(sizes)} > {max_total_bytes}")


def locate(path: str | Path, name: str, *, part: str = "both", fuzzy: bool = False,
           include_source: bool = False, max_members: int = DEFAULT_MAX_MEMBERS,
           max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
           max_member_bytes: int = DEFAULT_MAX_MEMBER_BYTES) -> dict:
    reader = None
    try:
        reader = _Reader(Path(path), max_members=max_members,
                         max_total_bytes=max_total_bytes, max_member_bytes=max_member_bytes)
        oems = [items[0] for key, items in reader.members.items()
                if PurePosixPath(items[0]["path"]).suffix.lower() == ".oem"]
        if len(oems) != 1:
            return {"status": "missing_oem" if not oems else "ambiguous_oem", "branches": {}}
        oem = oems[0]
        oem_size = oem["size"] if "size" in oem else oem["info"].file_size
        if oem_size > OEM_LIMIT:
            return {"status": "oem_size_budget_exceeded", "branches": {}}
        root = _xml(reader.read(oem), oem["path"])
        namespace = _check_tree(root)
        if not _tag(root, namespace, "sysmac") or root.attrib.get("schemaVersion") != "1":
            return {"status": "unsupported_layout", "branches": {}}
        entities, layout = _collect_entities(root, namespace)
        if not layout:
            return {"status": "unsupported_layout", "branches": {}}
        ids: dict[str, list[ET.Element]] = {}
        for entity in entities:
            if entity.get("id"):
                identifier = entity.get("id")
                ids.setdefault(canonical_guid(identifier) or "raw:" + identifier, []).append(entity)
        duplicates = sorted(identifier for identifier, group in ids.items() if len(group) > 1)
        if duplicates:
            return {"status": "duplicate_id", "duplicate_ids": duplicates, "branches": {}}
        definitions, named = _definitions(name, entities)
        if fuzzy:
            candidates = sorted({entity.get("name", "") for entity in entities
                                 if entity.get("type") == "FunctionBlock" and
                                 entity.get("subtype", "").lower() in {"structuredtext", "st"} and
                                 name.casefold() in entity.get("name", "").casefold()})
            return {"status": "candidates_only", "candidates": candidates,
                    "opened_oem": oem["path"], "source_opened": False, "branches": {}}
        if not definitions:
            return {"status": "object_not_found" if not named else "unsupported_definition_type",
                    "candidates": [{"name": item.get("name"), "type": item.get("type"),
                                    "id": item.get("id"), "path": _path_for(item, entities, namespace)}
                                   for item in named], "branches": {}}
        if len(definitions) != 1:
            return {"status": "ambiguous_definition",
                    "candidates": [{"id": item.get("id"), "path": _path_for(item, entities, namespace)}
                                   for item in definitions], "branches": {}}
        definition = definitions[0]
        definition_guid = canonical_guid(definition.get("id"))
        if not definition_guid:
            return {"status": "invalid_definition_guid", "branches": {}}
        guid_index: dict[str, list] = {}
        for items in reader.members.values():
            for item in items:
                basename = PurePosixPath(item["path"]).name
                if PurePosixPath(basename).suffix.casefold() == ".xml":
                    member_guid = canonical_guid(PurePosixPath(basename).stem)
                    if member_guid:
                        guid_index.setdefault(member_guid, []).append(item)
        roles: dict[str, list[ET.Element]] = {}
        for child in _entity_children(definition, namespace):
            for role_name, (role_type, _) in ROLES.items():
                if child.get("type") == role_type:
                    roles.setdefault(role_name, []).append(child)
        branches = {}
        for role_name in ("variables", "body"):
            if part not in ("both", role_name):
                branches[role_name] = {"status": "not_requested"}
                continue
            selected_roles = roles.get(role_name, [])
            if len(selected_roles) > 1:
                branches[role_name] = {"status": "ambiguous_role",
                                       "role_ids": [item.get("id") for item in selected_roles]}
            else:
                branches[role_name] = _branch(selected_roles[0] if selected_roles else None,
                                              role_name, namespace, reader.members, guid_index,
                                              reader.read, include_source)
        statuses = [item["status"] for item in branches.values() if item["status"] != "not_requested"]
        top_status = "complete" if statuses and all(status == "complete" for status in statuses) else "partial"
        return {"status": top_status, "oem_path": oem["path"],
                "definition": {"name": name, "type": definition.get("type"),
                               "subtype": definition.get("subtype"), "id": definition_guid,
                               "path": _path_for(definition, entities, namespace)},
                "namespace": namespace or None, "entity_root_layout": layout,
                "role_layout": "direct Entity children in same-namespace ChildEntities",
                "branches": branches,
                "source_text_semantics": "XML Text nodes are decoded logical text; XML line endings are normalized"}
    except LocateError as exc:
        message = str(exc)
        status, _, detail = message.partition(": ")
        return {"status": status, "detail": detail, "branches": {}}
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        return {"status": "input_error", "detail": str(exc), "branches": {}}
    finally:
        if reader:
            reader.close()


_VARIABLE_HEADERS = ("变量名", "类型", "声明组/方向", "初值", "地址/属性", "原注释")
_GROUP_LABELS = {"VAR_INPUT": "输入", "VAR_OUTPUT": "输出", "VAR_IN_OUT": "输入输出",
                 "VAR": "内部变量", "VAR_GLOBAL": "全局声明组"}
_SOURCE_MARKER = re.compile(r"(?m)^<!-- plc-source:(\{[^\n]*\}) -->\n\n")


def _md_cell(value: str) -> str:
    """Escape display text only; preserved source blocks never pass here."""
    escaped = (html.escape(str(value), quote=False).replace("|", "&#124;")
               .replace("`", "&#96;"))
    escaped = escaped.translate({ord(char): f"&#{ord(char)};" for char in "\\*_[]()!~"})
    return escaped.replace("\r\n", "<br>").replace("\r", "<br>").replace("\n", "<br>")


def _variable_records(source: str | None) -> list[tuple[str, ...]] | None:
    if source is None or not any(line.startswith("++D=") for line in source.splitlines()):
        return None
    lines = source.splitlines()
    group = None
    records = []
    for line in lines[1:]:
        if line.startswith("+GN="):
            group = line.split("\t", 1)[0].partition("=")[2]
        elif line.startswith("++D="):
            fields = {key: value for token in line.split("\t")
                      for key, _, value in [token.partition("=")]}
            selected_group = fields.get("G", group) or "未提供"
            display_group = _GROUP_LABELS.get(selected_group)
            display_group = (display_group + "（" + selected_group + "）") if display_group else selected_group
            # No vendor-wide initial-value field mapping has been verified. Preserve
            # unclassified keyed attributes explicitly instead of guessing semantics.
            attributes = "；".join(f"{key}={value}" for key, value in fields.items()
                                   if key not in {"++D", "N", "G", "Com"}) or "未提供"
            records.append((fields["N"], fields["++D"], display_group, "未提供/未判定",
                            attributes, fields.get("Com") or "未提供"))
    return records


def _variable_section(source: str | None) -> str:
    if source is None:
        return "本次未请求变量声明。\n"
    records = _variable_records(source)
    if records is None:
        return "未转换为变量表：当前声明不属于已识别的记录式载荷，完整原始声明见下方核对区。\n"
    out = [f"按原声明顺序整理 {len(records)} 条记录；方向只依据声明组，不按变量名推断。",
           "初值字段语义尚未确认时不猜测，未分类属性保留原字段名；完整原文仍在下方。", "",
           "| " + " | ".join(_VARIABLE_HEADERS) + " |", "|---|---|---|---|---|---|"]
    out.extend("| " + " | ".join(_md_cell(value) for value in record) + " |" for record in records)
    return "\n".join(out) + "\n"


def _source_block(role: str, source: str) -> str:
    longest = max((len(item) for item in re.findall(r"`+", source)), default=0)
    fence = "`" * max(3, longest + 1)
    meta = {"role": role, "characters": len(source),
            "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "separator_newline": not source.endswith("\n")}
    marker = json.dumps(meta, ensure_ascii=True, separators=(",", ":"))
    language = "text" if role == "variables" else "iecst"
    return ("<!-- plc-source:" + marker + " -->\n\n" + fence + language + "\n" + source
            + ("\n" if meta["separator_newline"] else "") + fence + "\n")


def extract_source_blocks(document: str) -> dict[str, str]:
    """Read our exported blocks exactly, including CRLF and a missing EOF newline."""
    found = {}
    cursor = 0
    while match := _SOURCE_MARKER.search(document, cursor):
        meta = json.loads(match[1])
        role = meta.get("role")
        size = meta.get("characters")
        if (role not in ROLES or role in found or type(size) is not int or size < 0
                or type(meta.get("separator_newline")) is not bool):
            raise ValueError("invalid or duplicate source metadata")
        opening = re.match(r"(`{3,})(text|iecst)\n", document[match.end():])
        if opening is None or opening[2] != ("text" if role == "variables" else "iecst"):
            raise ValueError("source fence opening is missing")
        start = match.end() + opening.end()
        source = document[start:start + size]
        suffix = ("\n" if meta["separator_newline"] else "") + opening[1] + "\n"
        if (len(source) != size or document[start + size:start + size + len(suffix)] != suffix
                or meta["separator_newline"] != (not source.endswith("\n"))
                or hashlib.sha256(source.encode("utf-8")).hexdigest() != meta.get("sha256")):
            raise ValueError("source length, hash or fence does not match")
        # A closing-sized delimiter inside source would corrupt human rendering.
        if re.search(r"(?m)^ {0,3}" + re.escape(opening[1]) + r"`*[ \t]*(?:\r?$)", source):
            raise ValueError("source fence collides with source text")
        found[role] = source
        cursor = start + size + len(suffix)
    if not found:
        raise ValueError("no source blocks in Markdown")
    return found


def validate_export(document: str, result: dict) -> dict:
    """Validate read-back against independently extracted text, not a new plan."""
    if result.get("status") != "complete":
        raise ValueError("cannot validate incomplete extraction as a complete export")
    if any(item.get("status") not in {"complete", "not_requested"}
           or (item.get("status") == "complete" and not isinstance(item.get("source"), str))
           for item in result["branches"].values()):
        raise ValueError("a requested branch is incomplete or lacks source")
    expected = {role: branch["source"] for role, branch in result["branches"].items()
                if branch.get("status") == "complete" and isinstance(branch.get("source"), str)}
    if not expected or extract_source_blocks(document) != expected:
        raise ValueError("source scope or characters differ from extraction")
    visible_parts = []
    cursor = 0
    while match := _SOURCE_MARKER.search(document, cursor):
        meta = json.loads(match[1])
        opening = re.match(r"(`{3,})(text|iecst)\n", document[match.end():])
        assert opening is not None  # The exact source-block check above already passed.
        visible_parts.append(document[cursor:match.start()])
        cursor = match.end() + opening.end() + meta["characters"] + len(opening[1]) + 1
        if meta["separator_newline"]:
            cursor += 1
    visible_parts.append(document[cursor:])
    display_document = "".join(visible_parts)
    begin, end = "<!-- plc-variable-view:start -->\n\n", "\n<!-- plc-variable-view:end -->"
    if display_document.count(begin) != 1 or display_document.count(end) != 1:
        raise ValueError("variable display boundary is missing or repeated")
    view = display_document.split(begin, 1)[1].split(end, 1)[0]
    if view != _variable_section(expected.get("variables")):
        raise ValueError("variable table does not match source records")
    records = _variable_records(expected.get("variables"))
    if records is not None:
        from markdown_it import MarkdownIt
        tokens = MarkdownIt("commonmark").enable("table").parse(view)
        rendered_cells = []
        for index, token in enumerate(tokens):
            if token.type == "td_open":
                children = tokens[index + 1].children or []
                if not children or any(child.type != "text" for child in children):
                    raise ValueError("a variable value became Markdown markup")
                rendered_cells.append("".join(child.content for child in children))
        if rendered_cells != [value for record in records for value in record]:
            raise ValueError("rendered variable text differs from source fields")
    anchors = re.findall(r'(?m)^<a id="([a-z-]+)"></a>$', display_document)
    required = {"source-scope", "validation"} | ({"st-body"} if "body" in expected else set()) | ({"variables", "original-variables"} if "variables" in expected else set())
    if len(anchors) != len(set(anchors)) or set(anchors) != required:
        raise ValueError("document anchors or requested sections are invalid")
    return {"source_equal": True, "scope_equal": True, "variable_view_equal": True,
            "structure_checked": True}


def _render_markdown(result: dict, input_path: Path) -> str:
    branches = result["branches"]
    source = {role: item["source"] for role, item in branches.items()
              if item.get("status") == "complete" and isinstance(item.get("source"), str)}
    definition = result["definition"]
    out = ["# " + _md_cell(definition["name"]) + " — 源码资料", "",
           "> 工程：" + _md_cell(input_path.name), "> 讲解深度：源码提取，未附讲解", "",
           '<a id="source-scope"></a>', "", "## 提取范围", "",
           "- 工程：" + _md_cell(input_path.name),
           "- 对象：" + _md_cell(definition["name"]),
           "- 类型/语言：" + _md_cell(str(definition.get("type"))) + " / " + _md_cell(str(definition.get("subtype"))),
           "- 来源描述：" + _md_cell(result["oem_path"]),
           "- 身份与归属：" + _md_cell(str(definition.get("path", definition["id"]))),
           "- 内容是经定位核对的提取文本；XML 实体与换行按 XML 规则解码，不等同原成员字节。"]
    for role, title in (("variables", "变量声明"), ("body", "程序体")):
        if role in source:
            out.append("- " + title + "来源：" + _md_cell(branches[role]["member_path"]))
    if "variables" in source:
        out += ["", '<a id="variables"></a>', "", "## 变量声明", ""]
    out += ["<!-- plc-variable-view:start -->\n\n" + _variable_section(source.get("variables")) + "\n<!-- plc-variable-view:end -->", ""]
    if "body" in source:
        out += ['<a id="st-body"></a>', "", "## ST 程序体", "",
                _source_block("body", source["body"])]
    out += ['<a id="validation"></a>', "", "## 完整性说明与校验结果", "",
            "- 源码一致性：通过。发布前写后回读，逐块核对字符、换行、末行状态和摘要；不改名、不重排、不补注。",
            "- 范围完整性：通过。仅导出本次请求且已完成的分支；未请求内容不表示已经读取。",
            "- Markdown 结构：通过。实际执行现有严格渲染检查，源码围栏、分区锚点与请求分支一致。",
            "- 变量可读化：表格一致性已核对；不适用时明确标记未转换，不把原声明替换成推测结果。",
            "- PLC 编译、仿真与实机检测：未执行。上述机械校验不证明程序运行正确。",
            "- 后续操作：本文件为只读源码底稿，按用户原任务继续；讲解或修改结果另存。", ""]
    if "variables" in source:
        out += ['<a id="original-variables"></a>', "", "## 原始声明（保真核对）", "",
                "以下完整保留声明载荷中的原字段和符号，供后续查证，不用表格替代原文。", "",
                _source_block("variables", source["variables"])]
    return "\n".join(out)


def export_markdown(result: dict, input_path: Path, output_path: Path) -> dict:
    """Publish one verified UTF-8 Markdown artifact without replacing any file."""
    if result.get("status") != "complete":
        raise ValueError("only a complete extraction can be exported")
    output_path = output_path.absolute()
    if output_path.suffix.casefold() != ".md":
        raise ValueError("output must use the .md extension")
    if os.path.lexists(output_path):
        raise FileExistsError("output already exists; select a new filename")
    parent = output_path.parent.resolve(strict=True)
    destination = parent / output_path.name
    skill_root = Path(__file__).resolve().parents[1]
    if destination.is_relative_to(skill_root):
        raise ValueError("output must be outside the skill directory")
    source_path = input_path.resolve(strict=True)
    if destination == source_path or (source_path.is_dir() and destination.is_relative_to(source_path)):
        raise ValueError("output must not replace or enter the input")
    document = _render_markdown(result, input_path)
    temporary = None
    try:
        fd, temporary_name = tempfile.mkstemp(prefix="." + output_path.name + ".", suffix=".tmp", dir=parent)
        temporary = Path(temporary_name)
        with os.fdopen(fd, "wb") as stream:
            stream.write(document.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        raw = temporary.read_bytes()
        checks = validate_export(raw.decode("utf-8"), result)
        markdown = subprocess.run(
            [sys.executable, "-B", str(Path(__file__).resolve().with_name("check_markdown_format.py")),
             str(temporary), "--strict", "--json"], capture_output=True, text=True, timeout=60, check=False)
        if markdown.returncode:
            raise ValueError("Markdown render validation failed: " + (markdown.stdout + markdown.stderr)[-700:])
        format_result = json.loads(markdown.stdout)
        checks["markdown_rendered"] = True
        checks["markdown_warning_count"] = len(format_result.get("warnings", []))
        # link creates the destination exclusively; an existing file is never replaced.
        os.link(temporary, destination)
        digest = hashlib.sha256(raw).hexdigest()
        return {"path": str(destination), "filename": destination.name,
                "bytes": len(raw), "sha256": digest, "verified": True, "checks": checks,
                "sections": {**{role: ("variables" if role == "variables" else "st-body")
                                 for role, item in result["branches"].items() if item["status"] == "complete"},
                             "validation": "validation"}}
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="SMC2 ZIP or approved unpacked directory")
    parser.add_argument("name", help="exact FunctionBlock definition name")
    parser.add_argument("--part", choices=("body", "variables", "both"), default="both")
    parser.add_argument("--fuzzy", action="store_true", help="list definition-name candidates only")
    parser.add_argument("--output-md", type=Path, help="write one complete verified Markdown; stdout stays compact")
    parser.add_argument("--include-source", action="store_true", help="include requested verified source text")
    parser.add_argument("--max-members", type=int, default=DEFAULT_MAX_MEMBERS)
    parser.add_argument("--max-total-bytes", type=int, default=DEFAULT_MAX_TOTAL_BYTES)
    parser.add_argument("--max-member-bytes", type=int, default=DEFAULT_MAX_MEMBER_BYTES)
    args = parser.parse_args(argv)
    if not args.name or min(args.max_members, args.max_total_bytes, args.max_member_bytes) <= 0:
        parser.error("name and budget values must be non-empty/positive")
    if args.output_md and args.fuzzy:
        parser.error("argument --output-md: not allowed with argument --fuzzy")
    result = locate(args.input, args.name, part=args.part, fuzzy=args.fuzzy,
                    include_source=args.include_source or bool(args.output_md), max_members=args.max_members,
                    max_total_bytes=args.max_total_bytes, max_member_bytes=args.max_member_bytes)
    if args.output_md:
        summary = {"status": result["status"], "export_status": "not_generated",
                   "branches": {role: item["status"] for role, item in result.get("branches", {}).items()},
                   "exported_branches": [], "next_action": "resolve_extraction"}
        if result["status"] == "complete":
            try:
                summary["artifact"] = export_markdown(result, args.input, args.output_md)
                summary.update(export_status="complete", next_action="continue_original_task",
                               exported_branches=[role for role, item in result["branches"].items()
                                                  if item["status"] == "complete"])
            except (OSError, ValueError, KeyError, TypeError, ImportError, subprocess.SubprocessError) as exc:
                summary.update(export_status="failed", next_action="resolve_export", error=str(exc)[:600])
        print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
        return 0 if summary["export_status"] == "complete" else 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0 if result["status"] == "complete" or result["status"] == "candidates_only" else 2


if __name__ == "__main__":
    raise SystemExit(main())
