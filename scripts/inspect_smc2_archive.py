#!/usr/bin/env python3
"""Inventory SMC2 ZIP archives without extracting their contents."""

from __future__ import annotations

import argparse
import codecs
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

MAX_METADATA_BYTES = 8 * 1024 * 1024
DEFAULT_MAX_MEMBERS = 5000
DEFAULT_MAX_TOTAL_BYTES = 512 * 1024 * 1024
DEFAULT_MAX_MEMBER_BYTES = 256 * 1024 * 1024
XML_EXTENSIONS = {".oem", ".xml"}
METADATA_OK = {"xml-ok", "json-ok"}
DTD_OR_ENTITY = re.compile(r"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)


def safe_member_name(name: str) -> bool:
    if not name or "\x00" in name:
        return False
    # Windows 盘符成员（C:/x、C:\x、C:x）在 Posix 路径语义下看似相对路径。
    if re.match(r"^[A-Za-z]:", name):
        return False
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts and "\\" not in name


def decode_xml(raw: bytes) -> str:
    """按 BOM 或无 BOM 的 NUL 模式解码，供 DTD/ENTITY 文本检查使用。"""
    if raw.startswith(codecs.BOM_UTF32_LE) or raw.startswith(codecs.BOM_UTF32_BE):
        return raw.decode("utf-32")
    if raw.startswith(codecs.BOM_UTF16_LE) or raw.startswith(codecs.BOM_UTF16_BE):
        return raw.decode("utf-16")
    if raw.startswith(codecs.BOM_UTF8):
        return raw.decode("utf-8-sig")
    head = raw[:4]
    if head == b"<\x00\x00\x00":
        return raw.decode("utf-32-le")
    if head == b"\x00\x00\x00<":
        return raw.decode("utf-32-be")
    if head[:2] == b"<\x00":
        return raw.decode("utf-16-le")
    if head[:2] == b"\x00<":
        return raw.decode("utf-16-be")
    return raw.decode("utf-8-sig")


def check_xml(raw: bytes) -> str:
    try:
        text = decode_xml(raw)
    except UnicodeDecodeError:
        # 声明为其它编码（如 GBK）时保留原字节交给 expat，仅用字节扫描查 DTD。
        text = raw.decode("latin-1")
        decoded = False
    else:
        decoded = True
    if DTD_OR_ENTITY.search(text):
        return "xml-rejected-dtd"
    try:
        ElementTree.fromstring(text if decoded else raw)
    except (ElementTree.ParseError, ValueError):
        return "parse-error"
    return "xml-ok"


def parse_status(
    archive: zipfile.ZipFile,
    name: str,
    size: int,
    max_metadata_bytes: int = MAX_METADATA_BYTES,
) -> str:
    suffix = PurePosixPath(name).suffix.lower()
    if suffix not in XML_EXTENSIONS | {".json"}:
        return "not-parsed"
    if size > max_metadata_bytes:
        return "too-large-to-parse"
    try:
        raw = archive.read(name)
    except (KeyError, RuntimeError, zipfile.BadZipFile):
        return "parse-error"
    if suffix == ".json":
        try:
            json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return "parse-error"
        return "json-ok"
    return check_xml(raw)


def metadata_summary(files: list[dict], limit: int) -> dict:
    eligible = [item for item in files if item["parse_status"] != "not-parsed"]
    skipped = [item["path"] for item in eligible if item["parse_status"] == "too-large-to-parse"]
    failed = [
        item["path"]
        for item in eligible
        if item["parse_status"] not in METADATA_OK and item["parse_status"] not in {"too-large-to-parse"}
    ]
    complete = not skipped and not failed
    return {
        "limit_bytes": limit,
        "eligible": len(eligible),
        "parsed_ok": sum(1 for item in eligible if item["parse_status"] in METADATA_OK),
        "skipped_too_large": skipped,
        "failed": failed,
        "status": "complete" if complete else "incomplete",
        "complete": complete,
    }


def enforce_budgets(
    infos: list[zipfile.ZipInfo],
    max_members: int,
    max_total_bytes: int,
    max_member_bytes: int,
) -> None:
    if len(infos) > max_members:
        raise ValueError(f"archive has {len(infos)} members, exceeds --max-members {max_members}")
    oversized = [info.filename for info in infos if info.file_size > max_member_bytes]
    if oversized:
        shown = ", ".join(oversized[:5]) + (" ..." if len(oversized) > 5 else "")
        raise ValueError(
            f"archive member exceeds --max-member-bytes {max_member_bytes}: {shown}"
        )
    total = sum(info.file_size for info in infos)
    if total > max_total_bytes:
        raise ValueError(
            f"archive declares {total} uncompressed bytes, exceeds --max-total-bytes {max_total_bytes}"
        )


def inventory(
    path: Path,
    *,
    max_members: int = DEFAULT_MAX_MEMBERS,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
    max_member_bytes: int = DEFAULT_MAX_MEMBER_BYTES,
    max_metadata_bytes: int = MAX_METADATA_BYTES,
) -> dict:
    if not zipfile.is_zipfile(path):
        raise ValueError("not a valid ZIP archive")
    with zipfile.ZipFile(path) as archive:
        infos = [info for info in archive.infolist() if not info.is_dir()]
        names = [info.filename for info in infos]
        duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
        if duplicates:
            raise ValueError("duplicate archive member: " + ", ".join(duplicates[:5]))
        unsafe = [name for name in names if not safe_member_name(name)]
        if unsafe:
            raise ValueError("unsafe archive member: " + ", ".join(unsafe[:5]))
        enforce_budgets(infos, max_members, max_total_bytes, max_member_bytes)
        extension_counts = Counter(PurePosixPath(name).suffix.lower() or "[no extension]" for name in names)
        files = [
            {
                "path": info.filename,
                "size": info.file_size,
                "extension": PurePosixPath(info.filename).suffix.lower(),
                "parse_status": parse_status(archive, info.filename, info.file_size, max_metadata_bytes),
            }
            for info in infos
        ]
    return {
        "archive": str(path.resolve()),
        "file_count": len(files),
        "extension_counts": dict(sorted(extension_counts.items())),
        "oem_files": [item["path"] for item in files if item["extension"] == ".oem"],
        "files": files,
        "parse_status": {item["path"]: item["parse_status"] for item in files},
        "metadata": metadata_summary(files, max_metadata_bytes),
        "note": (
            "Archive contents were inspected in place; no files were extracted. "
            "Metadata covers only .oem/.xml/.json; see metadata.complete and parse_status. "
            "OEM XML parsing does not infer project-specific hierarchy semantics."
        ),
    }


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an integer: {value!r}") from None
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return number


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="SMC2 archive readable as ZIP")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument(
        "--max-members", type=positive_int, default=DEFAULT_MAX_MEMBERS, metavar="N",
        help=f"reject archives with more than N members (default {DEFAULT_MAX_MEMBERS})",
    )
    parser.add_argument(
        "--max-total-bytes", type=positive_int, default=DEFAULT_MAX_TOTAL_BYTES, metavar="N",
        help="reject archives whose declared uncompressed size exceeds N bytes",
    )
    parser.add_argument(
        "--max-member-bytes", type=positive_int, default=DEFAULT_MAX_MEMBER_BYTES, metavar="N",
        help="reject any single member larger than N bytes",
    )
    parser.add_argument(
        "--max-metadata-bytes", type=positive_int, default=MAX_METADATA_BYTES, metavar="N",
        help=f"per-file XML/JSON parse limit in bytes (default {MAX_METADATA_BYTES})",
    )
    args = parser.parse_args(argv)
    try:
        result = inventory(
            args.archive,
            max_members=args.max_members,
            max_total_bytes=args.max_total_bytes,
            max_member_bytes=args.max_member_bytes,
            max_metadata_bytes=args.max_metadata_bytes,
        )
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Archive: {result['archive']}")
        print(f"Files: {result['file_count']}")
        print("Extensions:")
        for extension, count in result["extension_counts"].items():
            print(f"  {extension}: {count}")
        print("OEM files:")
        for name in result["oem_files"]:
            print(f"  {name}")
        print("Parse status:")
        for name, status in result["parse_status"].items():
            print(f"  {name}: {status}")
        metadata = result["metadata"]
        print(
            f"Metadata: {metadata['status']} "
            f"({metadata['parsed_ok']}/{metadata['eligible']} parsed; "
            f"limit {metadata['limit_bytes']} bytes/file)"
        )
        for name in metadata["skipped_too_large"]:
            print(f"  skipped (too large): {name}")
        for name in metadata["failed"]:
            print(f"  failed: {name}")
        print(result["note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
