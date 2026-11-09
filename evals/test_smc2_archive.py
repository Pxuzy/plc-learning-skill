#!/usr/bin/env python3
"""Regression tests for the SMC2 archive inventory helper."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import warnings
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "inspect_smc2_archive.py"


def run(*args: str):
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_inventory_reports_extensions_and_parse_status():
    with tempfile.TemporaryDirectory() as td:
        archive = Path(td) / "demo.smc2"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("Project.oem", "<Project><Task name=\"Main\"/></Project>")
            zf.writestr("Code/Section.st", "IF Enable THEN\n  Done := TRUE;\nEND_IF;")
            zf.writestr("Code/Section.xml", "<Section id=\"S1\"/>")
            zf.writestr("Config/settings.json", json.dumps({"ok": True}))
            zf.writestr("notes.txt", "ignored")
        result = run(str(archive), "--json")
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["archive"] == str(archive)
        assert data["file_count"] == 5
        assert data["extension_counts"][".oem"] == 1
        assert data["extension_counts"][".st"] == 1
        assert data["parse_status"]["Project.oem"] == "xml-ok"
        assert data["parse_status"]["Config/settings.json"] == "json-ok"
        assert data["parse_status"]["Code/Section.st"] == "not-parsed"


def test_inventory_rejects_non_archive_and_path_traversal_member():
    with tempfile.TemporaryDirectory() as td:
        plain = Path(td) / "not.smc2"
        plain.write_text("not a zip", encoding="utf-8")
        result = run(str(plain), "--json")
        assert result.returncode != 0
        assert "not a valid ZIP archive" in result.stderr

        archive = Path(td) / "unsafe.smc2"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("../escape.st", "bad")
        result = run(str(archive), "--json")
        assert result.returncode != 0
        assert "unsafe archive member" in result.stderr


def write_zip(path: Path, entries: list[tuple[str, str | bytes]]) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # 允许故意写入重名成员
        with zipfile.ZipFile(path, "w") as zf:
            for name, payload in entries:
                zf.writestr(name, payload)


def test_inventory_rejects_duplicate_members():
    with tempfile.TemporaryDirectory() as td:
        archive = Path(td) / "dup.smc2"
        write_zip(archive, [("Project.oem", "<Project/>"), ("Project.oem", "<Project/>")])
        result = run(str(archive), "--json")
        assert result.returncode != 0, result.stdout
        assert "duplicate archive member" in result.stderr, result.stderr


def test_inventory_rejects_dtd_and_entity_in_wide_encodings():
    body = '<!DOCTYPE Project [<!ENTITY boom "x">]><Project>&boom;</Project>'
    payloads = {
        "u16-bom.oem": body.encode("utf-16"),
        "u16-le.oem": body.encode("utf-16-le"),
        "u32-bom.xml": body.encode("utf-32"),
        "u32-be.xml": body.encode("utf-32-be"),
    }
    with tempfile.TemporaryDirectory() as td:
        archive = Path(td) / "wide.smc2"
        write_zip(archive, list(payloads.items()))
        result = run(str(archive), "--json")
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        for name in payloads:
            assert data["parse_status"][name] == "xml-rejected-dtd", (name, data["parse_status"])
        assert data["metadata"]["complete"] is False, data["metadata"]


def test_inventory_rejects_windows_drive_members():
    with tempfile.TemporaryDirectory() as td:
        for idx, name in enumerate(("C:/escape.st", "c:\\escape.st", "D:escape.st")):
            archive = Path(td) / f"drive{idx}.smc2"
            write_zip(archive, [(name, "bad")])
            result = run(str(archive), "--json")
            assert result.returncode != 0, (name, result.stdout)
            assert "unsafe archive member" in result.stderr, (name, result.stderr)


def test_inventory_enforces_member_and_byte_budgets():
    with tempfile.TemporaryDirectory() as td:
        archive = Path(td) / "budget.smc2"
        write_zip(archive, [("a.st", "abcde"), ("b.st", "abcde"), ("c.st", "abcde")])

        result = run(str(archive), "--json", "--max-members", "2")
        assert result.returncode != 0, result.stdout
        assert "max-members" in result.stderr, result.stderr

        result = run(str(archive), "--json", "--max-total-bytes", "12")
        assert result.returncode != 0, result.stdout
        assert "max-total-bytes" in result.stderr, result.stderr

        result = run(str(archive), "--json", "--max-member-bytes", "4")
        assert result.returncode != 0, result.stdout
        assert "max-member-bytes" in result.stderr, result.stderr

        result = run(str(archive), "--json", "--max-total-bytes", "15", "--max-member-bytes", "5")
        assert result.returncode == 0, result.stderr


def test_metadata_size_limit_is_explicit_and_raisable():
    big_xml = "<Root>" + "<Item/>" * 1_300_000 + "</Root>"
    with tempfile.TemporaryDirectory() as td:
        archive = Path(td) / "large.smc2"
        write_zip(archive, [("Project.oem", big_xml)])

        result = run(str(archive), "--json")
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["parse_status"]["Project.oem"] == "too-large-to-parse", data["parse_status"]
        assert data["metadata"]["complete"] is False, data["metadata"]
        assert data["metadata"]["status"] == "incomplete", data["metadata"]
        assert data["metadata"]["skipped_too_large"] == ["Project.oem"], data["metadata"]

        text = run(str(archive))
        assert text.returncode == 0, text.stderr
        assert "incomplete" in text.stdout, text.stdout

        raised = run(str(archive), "--json", "--max-metadata-bytes", "16777216")
        assert raised.returncode == 0, raised.stderr
        data = json.loads(raised.stdout)
        assert data["parse_status"]["Project.oem"] == "xml-ok", data["parse_status"]
        assert data["metadata"]["complete"] is True, data["metadata"]
        assert data["metadata"]["status"] == "complete", data["metadata"]


def main() -> int:
    tests = [
        test_inventory_reports_extensions_and_parse_status,
        test_inventory_rejects_non_archive_and_path_traversal_member,
        test_inventory_rejects_duplicate_members,
        test_inventory_rejects_dtd_and_entity_in_wide_encodings,
        test_inventory_rejects_windows_drive_members,
        test_inventory_enforces_member_and_byte_budgets,
        test_metadata_size_limit_is_explicit_and_raisable,
    ]
    failures = 0
    for test in tests:
        try:
            test()
        except Exception as exc:
            failures += 1
            print(f"FAIL {test.__name__}: {exc}")
        else:
            print(f"PASS {test.__name__}")
    print(f"{len(tests) - failures}/{len(tests)} passed")
    return int(failures > 0)


if __name__ == "__main__":
    raise SystemExit(main())
