#!/usr/bin/env python3
"""Synthetic behavioral tests for direct, read-only SMC2 POU lookup."""

from __future__ import annotations

import json
import contextlib
import html
import io
import os
import stat
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import smc2_locate_pou as locate  # noqa: E402


V_GUID = "12345678-1234-5678-1234-567812345678"
B_GUID = "87654321-4321-8765-4321-876543218765"
DEF_GUID = "dddddddd-dddd-dddd-dddd-dddddddddddd"
INSTANCE_GUID = "11111111-1111-1111-1111-111111111111"
V_HOLDER_GUID = "22222222-2222-2222-2222-222222222222"
B_HOLDER_GUID = "33333333-3333-3333-3333-333333333333"


def xml_fixture(*, namespace="urn:synthetic", duplicate=False, instance=False,
                holder=False, conflict=False, variables_name="Variables",
                body_name="PouBody", variables_type="Variables", body_type="PouBody",
                variables_holder_name="SourceHolder",
                body_holder_name="PouBodySourceHolder"):
    variables_name_attr = f' name="{variables_name}"' if variables_name is not None else ""
    body_name_attr = f' name="{body_name}"' if body_name is not None else ""
    role_variables = (f'<Entity{variables_name_attr} type="{variables_type}" '
                      f'id="{V_GUID}" />')
    role_body = f'<Entity{body_name_attr} type="{body_type}" id="{B_GUID}" />'
    if holder:
        role_variables = (f'<Entity{variables_name_attr} type="{variables_type}" id="{V_GUID}">'
                          f'<ChildEntities><Entity name="{variables_holder_name}" type="SourceHolder" '
                          f'id="{V_HOLDER_GUID}" SourcePath="decl/vars-source.xml" /></ChildEntities></Entity>')
        role_body = (f'<Entity{body_name_attr} '
                     f'type="{body_type}" id="{B_GUID}"><ChildEntities>'
                     f'<Entity name="{body_holder_name}" '
                     f'type="PouBodySourceHolder" id="{B_HOLDER_GUID}" SourcePath="body/body-source.xml" />'
                     '</ChildEntities></Entity>')
    if conflict:
        role_body = role_body.replace(f'id="{B_GUID}"', f'id="{B_GUID}" SourcePath="body/other.xml"')
    definition = (f'<Entity name="PumpLogic" type="FunctionBlock" subtype="StructuredText" '
                  f'id="{DEF_GUID}"><ChildEntities>' + role_variables + role_body +
                  '</ChildEntities></Entity>')
    items = definition
    if instance:
        items += f'<Entity name="PumpLogic" type="FunctionBlockInstance" id="{INSTANCE_GUID}" />'
    if duplicate:
        items += definition.replace(DEF_GUID, "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee").replace(V_GUID, "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa").replace(B_GUID, "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    return (f'<sysmac xmlns="{namespace}" schemaVersion="1"><ChildEntities>{items}'
            '</ChildEntities></sysmac>')


def top_level_entity_fixture(**kwargs):
    namespace = kwargs.get("namespace", "urn:synthetic")
    xml = xml_fixture(**kwargs)
    return xml.replace(f'<sysmac xmlns="{namespace}" schemaVersion="1"><ChildEntities>',
                       f'<sysmac xmlns="{namespace}" schemaVersion="1">', 1).replace(
                           '</ChildEntities></sysmac>', '</sysmac>', 1)


VARS = '[SLWD version=1.0]\nVAR_INPUT\n  Enable : BOOL;\nEND_VAR\n'
BODY = '<StructuredTextModel><Text>IF Enable THEN\n  Output := TRUE;\nEND_IF;</Text></StructuredTextModel>'


def entries(**kwargs):
    mapping = {
        "Project.oem": xml_fixture(**kwargs),
        f"decl/{V_GUID}.xml": VARS,
        f"body/{B_GUID}.xml": BODY,
        "body/other.xml": BODY,
    }
    if kwargs.get("holder"):
        mapping["decl/vars-source.xml"] = VARS
        mapping["body/body-source.xml"] = BODY
    return mapping


def make_zip(path, mapping):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(path, "w") as archive:
            for name, data in mapping.items():
                archive.writestr(name, data)


class LocatePouTests(unittest.TestCase):
    def run_lookup(self, path, *args):
        return locate.locate(path, "PumpLogic", part="both", **dict(args))

    def test_zip_direct_roles_and_exact_logical_source(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "synthetic.smc2"
            mapping = entries(instance=True)
            declarations = VARS.replace("\n", "\r\n")
            mapping[f"decl/{V_GUID}.xml"] = declarations
            mapping["Project.oem"] = mapping["Project.oem"].replace(
                f'<Entity name="Variables" type="Variables" id="{V_GUID}" />',
                f'<Entity name="Variables" type="Variables" id="{V_GUID}"><ChildEntities>'
                '<Entity name="PouIFLibraryHolder" type="PouIFLibraryHolder" id="H-LIB" />'
                '<Entity name="SourceHolder" type="SourceHolder" id="H-V" />'
                '</ChildEntities></Entity>',
            )
            make_zip(archive, mapping)
            opened = []
            original = zipfile.ZipFile.open

            def tracked(zf, name, *args, **kwargs):
                if isinstance(name, zipfile.ZipInfo):
                    name = name.filename
                opened.append(name)
                return original(zf, name, *args, **kwargs)

            with patch.object(zipfile.ZipFile, "open", tracked):
                result = locate.locate(archive, "PumpLogic", part="both", include_source=True)
            self.assertEqual(opened, ["Project.oem", f"decl/{V_GUID}.xml", f"body/{B_GUID}.xml"])
            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["branches"]["body"]["source"], "IF Enable THEN\n  Output := TRUE;\nEND_IF;")
            self.assertEqual(result["branches"]["variables"]["source"], declarations)
            self.assertIn("XML", result["source_text_semantics"])

    def test_distinct_supported_root_layout_fixtures(self):
        with tempfile.TemporaryDirectory() as temp:
            for filename, fixture, expected in (
                ("container.smc2", xml_fixture(), "root_child_entities"),
                ("top-level.smc2", top_level_entity_fixture(), "root_entity"),
            ):
                archive = Path(temp) / filename
                mapping = entries()
                mapping["Project.oem"] = fixture
                make_zip(archive, mapping)
                self.assertEqual(locate.locate(archive, "PumpLogic")["entity_root_layout"], expected)

    def test_role_type_survives_localized_and_missing_display_names(self):
        with tempfile.TemporaryDirectory() as temp:
            for index, (variables_name, body_name) in enumerate((
                ("Variables", "PouBody"),
                ("变量", "程序体"),
                (None, None),
            )):
                archive = Path(temp) / f"role-names-{index}.smc2"
                make_zip(archive, entries(variables_name=variables_name, body_name=body_name))
                result = locate.locate(archive, "PumpLogic", part="both")
                with self.subTest(variables_name=variables_name, body_name=body_name):
                    self.assertEqual(result["status"], "complete")
                    self.assertEqual(result["branches"]["variables"]["status"], "complete")
                    self.assertEqual(result["branches"]["body"]["status"], "complete")

    def test_english_role_display_name_with_wrong_type_is_not_selected(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "misleading-role-name.smc2"
            make_zip(archive, entries(variables_type="SourceHolder"))
            result = locate.locate(archive, "PumpLogic", part="both")
            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["branches"]["variables"]["status"], "role_missing")
            self.assertEqual(result["branches"]["body"]["status"], "complete")

    def test_duplicate_roles_of_the_same_type_remain_ambiguous(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "duplicate-role.smc2"
            xml = xml_fixture().replace(
                f'<Entity name="PouBody" type="PouBody" id="{B_GUID}" />',
                f'<Entity name="PouBody" type="PouBody" id="{B_GUID}" />'
                '<Entity name="Variables localized" type="Variables" '
                'id="44444444-4444-4444-4444-444444444444" />')
            mapping = entries()
            mapping["Project.oem"] = xml
            make_zip(archive, mapping)
            result = locate.locate(archive, "PumpLogic", part="both")
            self.assertEqual(result["branches"]["variables"]["status"], "ambiguous_role")
            self.assertEqual(result["branches"]["body"]["status"], "complete")

    def test_root_level_guid_member_is_selected(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "root-guid.smc2"
            mapping = entries()
            mapping.pop(f"body/{B_GUID}.xml")
            mapping[f"{B_GUID}.xml"] = BODY
            make_zip(archive, mapping)
            result = locate.locate(archive, "PumpLogic", part="body")
            self.assertEqual(result["branches"]["body"]["status"], "complete")
            self.assertEqual(result["branches"]["body"]["member_path"], f"{B_GUID}.xml")

    def test_explicit_relative_path_without_directory_does_not_fall_back(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "explicit.smc2"
            xml = xml_fixture().replace(
                f'<Entity name="PouBody" type="PouBody" id="{B_GUID}" />',
                f'<Entity name="PouBody" type="PouBody" id="{B_GUID}" SourcePath="other.xml" />')
            self.assertIn('SourcePath="other.xml"', xml)
            mapping = entries()
            mapping["Project.oem"] = xml
            mapping.pop(f"body/{B_GUID}.xml")
            make_zip(archive, mapping)
            result = locate.locate(archive, "PumpLogic", part="body")
            self.assertEqual(result["branches"]["body"]["status"], "unresolved_reference")

    def test_guid_duplicate_detection_normalizes_braces_and_case(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "duplicate-guid.smc2"
            xml = xml_fixture().replace(
                f'id="{B_GUID}"', f'id="{{{DEF_GUID.upper()}}}"')
            mapping = entries()
            mapping["Project.oem"] = xml
            make_zip(archive, mapping)
            self.assertEqual(locate.locate(archive, "PumpLogic")["status"], "duplicate_id")

    def test_nested_structured_text_model_is_rejected_but_variables_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "wrapped-body.smc2"
            mapping = entries()
            mapping[f"body/{B_GUID}.xml"] = '<Wrapper>' + BODY + '</Wrapper>'
            make_zip(archive, mapping)
            result = locate.locate(archive, "PumpLogic", part="both")
            self.assertEqual(result["branches"]["body"]["status"], "invalid_content")
            self.assertEqual(result["branches"]["variables"]["status"], "complete")

    def test_cli_unknown_xml_encoding_is_json_error(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "unknown-encoding.smc2"
            mapping = entries()
            bad_xml = '<?xml version="1.0" encoding="x-unknown-codec"?>' + BODY
            mapping[f"body/{B_GUID}.xml"] = bad_xml
            make_zip(archive, mapping)
            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            result = subprocess.run(
                [sys.executable, "-B", "scripts/smc2_locate_pou.py", str(archive),
                 "PumpLogic", "--part", "both", "--include-source"], cwd=ROOT, env=env,
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 2)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "partial")
            self.assertEqual(payload["branches"]["body"]["status"], "invalid_content")
            self.assertEqual(payload["branches"]["variables"]["status"], "complete")
            self.assertEqual(payload["branches"]["variables"]["source"], VARS)
            self.assertNotIn("Traceback", result.stderr)

            mapping["Project.oem"] = '<?xml version="1.0" encoding="x-unknown-codec"?>' + xml_fixture()
            make_zip(archive, mapping)
            oem = subprocess.run(
                [sys.executable, "-B", "scripts/smc2_locate_pou.py", str(archive), "PumpLogic"],
                cwd=ROOT, env=env, capture_output=True, text=True, check=False,
            )
            self.assertEqual(oem.returncode, 2)
            self.assertEqual(json.loads(oem.stdout)["status"], "invalid_xml")
            self.assertNotIn("Traceback", oem.stderr)

    def test_directory_single_role_reads_oem_and_only_requested_member(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, value in entries().items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(value, encoding="utf-8")
            opened = []
            original = Path.open

            def tracked(path, *args, **kwargs):
                if path.is_file():
                    opened.append(path.relative_to(root).as_posix())
                return original(path, *args, **kwargs)

            with patch.object(Path, "open", tracked):
                result = locate.locate(root, "PumpLogic", part="body")
            self.assertEqual(opened, ["Project.oem", f"body/{B_GUID}.xml"])
            self.assertEqual(result["branches"]["variables"]["status"], "not_requested")

    def test_duplicate_definition_and_fuzzy_do_not_open_source(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "ambiguous.smc2"
            make_zip(archive, entries(duplicate=True))
            opened = []
            original = zipfile.ZipFile.open

            def tracked(zf, name, *args, **kwargs):
                opened.append(name.filename if isinstance(name, zipfile.ZipInfo) else name)
                return original(zf, name, *args, **kwargs)

            with patch.object(zipfile.ZipFile, "open", tracked):
                result = locate.locate(archive, "PumpLogic", part="both")
            self.assertEqual(opened, ["Project.oem"])
            self.assertEqual(result["status"], "ambiguous_definition")
            with patch.object(zipfile.ZipFile, "open", tracked):
                fuzzy = locate.locate(archive, "Pump", part="both", fuzzy=True)
            self.assertEqual(fuzzy["status"], "candidates_only")
            self.assertEqual(opened[-1], "Project.oem")
            self.assertNotIn("source", fuzzy["branches"])

    def test_unknown_layout_and_duplicate_ids_are_not_silent(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "unknown.smc2"
            make_zip(archive, {"Project.oem": '<sysmac schemaVersion="1"><Other/></sysmac>'})
            self.assertEqual(locate.locate(archive, "PumpLogic")["status"], "unsupported_layout")
            make_zip(archive, {"Project.oem": xml_fixture().replace(f'id="{B_GUID}"', f'id="{V_GUID}"')})
            self.assertEqual(locate.locate(archive, "PumpLogic")["status"], "duplicate_id")
            hidden = xml_fixture().replace('<ChildEntities><Entity name="PumpLogic"',
                                           '<ChildEntities><Other><Entity name="PumpLogic"', 1).replace(
                                               '</ChildEntities></sysmac>', '</Other></ChildEntities></sysmac>', 1)
            make_zip(archive, {"Project.oem": hidden})
            self.assertEqual(locate.locate(archive, "PumpLogic")["status"], "unsupported_layout")

    def test_missing_and_invalid_branch_content_are_explicit(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "bad.smc2"
            mapping = entries()
            del mapping[f"body/{B_GUID}.xml"]
            make_zip(archive, mapping)
            self.assertEqual(locate.locate(archive, "PumpLogic")["branches"]["body"]["status"], "missing_member")
            mapping[f"body/{B_GUID}.xml"] = '{"Text":"not XML"}'
            make_zip(archive, mapping)
            self.assertEqual(locate.locate(archive, "PumpLogic")["branches"]["body"]["status"], "invalid_content")

    def test_holder_fallback_and_conflict(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "holder.smc2"
            mapping = entries(holder=True)
            mapping.pop(f"decl/{V_GUID}.xml")
            mapping.pop(f"body/{B_GUID}.xml")
            make_zip(archive, mapping)
            result = locate.locate(archive, "PumpLogic", part="both")
            self.assertEqual(result["branches"]["body"]["status"], "complete")
            self.assertEqual(result["branches"]["body"]["mapping_basis"], "holder_source_path")
            make_zip(archive, entries(holder=True, conflict=True))
            self.assertEqual(locate.locate(archive, "PumpLogic")["branches"]["body"]["status"], "reference_conflict")

    def test_localized_holder_display_names_keep_verified_path_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "localized-holder.smc2"
            mapping = entries(holder=True, variables_holder_name="变量来源",
                              body_holder_name="程序体来源")
            mapping.pop(f"decl/{V_GUID}.xml")
            mapping.pop(f"body/{B_GUID}.xml")
            make_zip(archive, mapping)
            result = locate.locate(archive, "PumpLogic", part="both")
            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["branches"]["variables"]["mapping_basis"], "holder_source_path")
            self.assertEqual(result["branches"]["body"]["mapping_basis"], "holder_source_path")

    def test_cli_fuzzy_and_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "unsafe.smc2"
            make_zip(archive, {"../escape": "x", "Project.oem": xml_fixture()})
            self.assertEqual(locate.locate(archive, "PumpLogic")["status"], "unsafe_path")

    def test_documented_script_entry_needs_no_pythonpath(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "cli.smc2"
            make_zip(archive, entries())
            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            result = subprocess.run(
                [sys.executable, "-B", "scripts/smc2_locate_pou.py", str(archive),
                 "PumpLogic", "--part", "body"], cwd=ROOT, env=env,
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)["branches"]["body"]["status"], "complete")

    def test_noise_members_and_ambiguous_text_never_open_unselected_source(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "noise.smc2"
            mapping = entries()
            mapping.update({f"noise/{index}.bin": b"x" for index in range(1000)})
            make_zip(archive, mapping)
            opened = []
            original = zipfile.ZipFile.open

            def tracked(zf, name, *args, **kwargs):
                name = name.filename if isinstance(name, zipfile.ZipInfo) else name
                opened.append(name)
                return original(zf, name, *args, **kwargs)

            with patch.object(zipfile.ZipFile, "open", tracked):
                body_only = locate.locate(archive, "PumpLogic", part="body")
            self.assertEqual(opened, ["Project.oem", f"body/{B_GUID}.xml"])
            self.assertEqual(body_only["branches"]["body"]["status"], "complete")
            self.assertEqual(body_only["branches"]["variables"]["status"], "not_requested")

            mapping[f"body/{B_GUID}.xml"] = (
                '<StructuredTextModel><Text>first</Text><Text>second</Text></StructuredTextModel>')
            make_zip(archive, mapping)
            opened.clear()
            with patch.object(zipfile.ZipFile, "open", tracked):
                both = locate.locate(archive, "PumpLogic", part="both")
            self.assertEqual(opened, ["Project.oem", f"decl/{V_GUID}.xml", f"body/{B_GUID}.xml"])
            self.assertEqual(both["branches"]["body"]["status"], "invalid_content")
            opened.clear()
            with patch.object(zipfile.ZipFile, "open", tracked):
                body = locate.locate(archive, "PumpLogic", part="body")
            self.assertEqual(opened, ["Project.oem", f"body/{B_GUID}.xml"])
            self.assertEqual(body["branches"]["variables"]["status"], "not_requested")

    def test_conflicting_reference_with_noise_does_not_search_or_open_other_members(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "conflicting-reference.smc2"
            mapping = entries(conflict=True)
            mapping.update({f"noise/{index}.bin": b"x" for index in range(1000)})
            make_zip(archive, mapping)
            opened = []
            original = zipfile.ZipFile.open

            def tracked(zf, name, *args, **kwargs):
                opened.append(name.filename if isinstance(name, zipfile.ZipInfo) else name)
                return original(zf, name, *args, **kwargs)

            with patch.object(zipfile.ZipFile, "open", tracked):
                result = locate.locate(archive, "PumpLogic", part="body")
            self.assertEqual(opened, ["Project.oem"])
            self.assertEqual(result["branches"]["body"]["status"], "reference_conflict")

    def test_preflight_rejects_duplicate_members_dtd_links_and_budgets(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "preflight.smc2"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(archive, "w") as zf:
                    zf.writestr("Project.oem", xml_fixture())
                    zf.writestr("Project.oem", xml_fixture())
            self.assertEqual(locate.locate(archive, "PumpLogic")["status"], "duplicate_member")

            make_zip(archive, {"Project.oem": '<!DOCTYPE sysmac><sysmac schemaVersion="1" />'})
            self.assertEqual(locate.locate(archive, "PumpLogic")["status"], "xml_rejected_dtd")
            with zipfile.ZipFile(archive, "w") as zf:
                info = zipfile.ZipInfo("link")
                info.create_system = 3
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                zf.writestr(info, "target")
                zf.writestr("Project.oem", xml_fixture())
            self.assertEqual(locate.locate(archive, "PumpLogic")["status"], "unsafe_path")
            make_zip(archive, entries())
            self.assertEqual(locate.locate(archive, "PumpLogic", max_members=2)["status"], "member_budget_exceeded")
            self.assertEqual(locate.locate(archive, "PumpLogic", max_member_bytes=10)["status"], "member_size_budget_exceeded")

    def test_directory_rejects_symlink_and_unrelated_namespace_entities(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, value in entries(namespace="urn:main").items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(value, encoding="utf-8")
            oem = root / "Project.oem"
            text = oem.read_text(encoding="utf-8")
            text = text.replace("</sysmac>", '<x:Entity xmlns:x="urn:other" name="PumpLogic" type="FunctionBlock" id="OTHER" /></sysmac>')
            oem.write_text(text, encoding="utf-8")
            self.assertEqual(locate.locate(root, "PumpLogic")["definition"]["id"], DEF_GUID)
            (root / "link.xml").symlink_to(root / "Project.oem")
            self.assertEqual(locate.locate(root, "PumpLogic")["status"], "unsafe_path")

    def test_wrong_role_holder_is_not_used_as_source_reference(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "wrong-holder.smc2"
            xml = xml_fixture().replace(
                f'<Entity name="PouBody" type="PouBody" id="{B_GUID}" />',
                f'<Entity name="PouBody" type="PouBody" id="{B_GUID}"><ChildEntities>'
                '<Entity name="SourceHolder" type="SourceHolder" id="WRONG" '
                'SourcePath="body/body-source.xml" /></ChildEntities></Entity>')
            mapping = entries()
            mapping["Project.oem"] = xml
            mapping["body/body-source.xml"] = BODY
            mapping.pop(f"body/{B_GUID}.xml")
            make_zip(archive, mapping)
            result = locate.locate(archive, "PumpLogic", part="body")
            self.assertEqual(result["branches"]["body"]["status"], "unresolved_reference")


class SlwdRecordPayloadTests(unittest.TestCase):
    HEADER = '[SLWD version=1.0]\n_EN=Variables\n'
    GROUP = '+GN=VAR_INPUT\tGVT=EdgeInputOutputGroup\n'
    RECORD = '++D=BOOL\tN=Enable\tG=VAR_INPUT\tCom=运行许可\n'

    def lookup(self, text):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / 'record-declarations.smc2'
            mapping = entries(variables_name='变量', body_name='程序体')
            mapping[f'decl/{V_GUID}.xml'] = text
            make_zip(archive, mapping)
            return locate.locate(archive, 'PumpLogic', part='variables', include_source=True)

    def test_record_declarations_are_preserved_including_extensions_and_crlf(self):
        text = self.HEADER + self.GROUP + self.RECORD.replace('\n', '\tExtensionFlag=sample-value\n')
        for source in (text, text.replace('\n', '\r\n')):
            with self.subTest(crlf='\r\n' in source):
                result = self.lookup(source)
                self.assertEqual(result['status'], 'complete')
                branch = result['branches']['variables']
                self.assertEqual(branch['source'], source)
                self.assertEqual(branch['content_coordinate'], 'whole member')
                self.assertEqual(result['branches']['body']['status'], 'not_requested')

    def test_record_group_can_be_inherited_without_a_g_field(self):
        source = self.HEADER + self.GROUP + self.RECORD.replace('\tG=VAR_INPUT', '')
        result = self.lookup(source)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['branches']['variables']['source'], source)

    def test_record_payload_rejects_missing_required_fields_and_truncation(self):
        for record in ('++D=BOOL\tG=VAR_INPUT\n',
                       '++D=\tN=Enable\tG=VAR_INPUT\n',
                       '++D=BOOL\tN=\tG=VAR_INPUT\n',
                       '++D=BOOL\tN=Enable\tG=\n',
                       '++D=BOOL\tN=Enable\tN=Other\tG=VAR_INPUT\n',
                       '++D=BOOL\tN\n'):
            with self.subTest(record=record):
                result = self.lookup(self.HEADER + self.GROUP + record)
                self.assertEqual(result['branches']['variables']['status'], 'invalid_content')

    def test_record_payload_rejects_garbage_empty_groups_and_nul(self):
        for source in (self.HEADER,
                       self.HEADER + self.GROUP,
                       self.HEADER + 'arbitrary declaration-looking garbage\n',
                       self.HEADER + self.GROUP + self.RECORD + 'unexpected record\n',
                       self.HEADER + self.GROUP + self.RECORD.replace('Enable', 'Ena\x00ble')):
            with self.subTest(source=source):
                self.assertEqual(self.lookup(source)['branches']['variables']['status'], 'invalid_content')


def body_xml(source):
    escaped = html.escape(source, quote=False).replace("\r", "&#13;")
    return f"<StructuredTextModel><Text>{escaped}</Text></StructuredTextModel>"


class MarkdownExportTests(unittest.TestCase):
    def run_cli(self, archive, *arguments, cwd=None, module=False):
        command = [sys.executable, "-B"]
        if module:
            command.extend(("-m", "scripts.smc2_locate_pou"))
        else:
            command.append(str(ROOT / "scripts/smc2_locate_pou.py"))
        command.extend((str(archive), "PumpLogic", *map(str, arguments)))
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        return subprocess.run(command, cwd=cwd or ROOT, env=env,
                              capture_output=True, text=True, check=False)

    def test_long_complete_export_is_one_verified_markdown_with_short_json(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "合成 工程.smc2"
            output = root / "完整源码.md"
            sentinel = "LONG_SOURCE_ONLY_SENTINEL_7f2a"
            source = "(* 原作者注释 / 控制程序 *)\r\n" + "".join(
                f"  Step_{index:04d} := {index}; {sentinel if index == 701 else ''}\r\n"
                for index in range(1200)
            ) + "  `inline` and ```fence``` and ~~~~\n\n"
            mapping = entries()
            mapping[f"decl/{V_GUID}.xml"] = VARS.replace("\n", "\r\n")
            mapping[f"body/{B_GUID}.xml"] = body_xml(source)
            make_zip(archive, mapping)

            result = self.run_cli(archive, "--output-md", output, "--include-source")

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual(summary["status"], "complete")
            self.assertEqual(summary["export_status"], "complete")
            self.assertEqual(summary["next_action"], "continue_original_task")
            self.assertTrue(summary["artifact"]["verified"])
            self.assertLess(len(result.stdout.encode("utf-8")), 8192)
            self.assertNotIn(sentinel, result.stdout)
            document = output.read_bytes().decode("utf-8")
            blocks = locate.extract_source_blocks(document)
            self.assertEqual(blocks, {"variables": mapping[f"decl/{V_GUID}.xml"], "body": source})
            self.assertIn("## 变量声明", document)
            self.assertIn("## ST 程序体", document)
            self.assertIn("## 完整性说明", document)

    def test_body_only_export_does_not_read_or_emit_variable_declarations(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "body-only.smc2"
            output = root / "body.md"
            source = "IF Enable THEN\n  Output := TRUE;\nEND_IF;"
            mapping = entries()
            mapping[f"body/{B_GUID}.xml"] = body_xml(source)
            make_zip(archive, mapping)

            result = self.run_cli(archive, "--part", "body", "--output-md", output)

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual(summary["exported_branches"], ["body"])
            self.assertEqual(summary["branches"]["variables"], "not_requested")
            self.assertEqual(locate.extract_source_blocks(output.read_bytes().decode("utf-8")),
                             {"body": source})
            self.assertNotIn("## 变量声明", output.read_bytes().decode("utf-8"))

    def test_text_boundaries_unicode_fences_and_isolated_python_calls(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cwd = root / "caller with space 中文"
            cwd.mkdir()
            (cwd / "scripts.py").write_text("raise RuntimeError('wrong scripts module')\n", encoding="utf-8")
            archive = root / "input file.smc2"
            output = root / "output file 中文.md"
            source = "(* Unicode 注释 *)\r\nIF A THEN\r\n  X := 1;\r\nEND_IF;`\n~~~\n"
            mapping = entries()
            mapping[f"decl/{V_GUID}.xml"] = VARS.replace("\n", "\r\n")
            mapping[f"body/{B_GUID}.xml"] = body_xml(source)
            make_zip(archive, mapping)

            result = self.run_cli(archive, "--output-md", output, cwd=cwd)

            self.assertEqual(result.returncode, 0, result.stderr)
            blocks = locate.extract_source_blocks(output.read_bytes().decode("utf-8"))
            self.assertEqual(blocks["body"], source)
            self.assertEqual(blocks["variables"], mapping[f"decl/{V_GUID}.xml"])

            module_result = self.run_cli(archive, cwd=ROOT, module=True)
            self.assertEqual(module_result.returncode, 0, module_result.stderr)
            self.assertEqual(json.loads(module_result.stdout)["status"], "complete")

    def test_legacy_json_modes_remain_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "legacy.smc2"
            make_zip(archive, entries())
            default = self.run_cli(archive)
            included = self.run_cli(archive, "--include-source")

            self.assertEqual(default.returncode, 0, default.stderr)
            self.assertEqual(included.returncode, 0, included.stderr)
            self.assertNotIn("export_status", json.loads(default.stdout))
            self.assertEqual(json.loads(included.stdout)["branches"]["body"]["source"],
                             "IF Enable THEN\n  Output := TRUE;\nEND_IF;")

    def test_partial_result_keeps_locator_status_and_does_not_publish(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "partial.smc2"
            output = root / "must-not-exist.md"
            mapping = entries()
            mapping.pop(f"body/{B_GUID}.xml")
            make_zip(archive, mapping)

            result = self.run_cli(archive, "--output-md", output)

            self.assertEqual(result.returncode, 2)
            summary = json.loads(result.stdout)
            self.assertEqual(summary["status"], "partial")
            self.assertEqual(summary["export_status"], "not_generated")
            self.assertFalse(output.exists())

    def test_fuzzy_cannot_be_combined_with_markdown_export(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "fuzzy.smc2"
            make_zip(archive, entries())

            result = self.run_cli(archive, "--fuzzy", "--output-md", Path(temp) / "x.md")

            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertIn("not allowed with argument --fuzzy", result.stderr)

    def test_existing_symlink_and_hardlinked_outputs_are_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "outputs.smc2"
            make_zip(archive, entries())
            regular = root / "existing.md"
            regular.write_text("keep", encoding="utf-8")
            symlink = root / "symlink.md"
            symlink.symlink_to(regular)
            hardlink = root / "hardlink.md"
            os.link(regular, hardlink)

            for output in (regular, symlink, hardlink):
                with self.subTest(output=output.name):
                    result = self.run_cli(archive, "--output-md", output)
                    summary = json.loads(result.stdout)
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(summary["export_status"], "failed")
                    self.assertEqual(regular.read_text(encoding="utf-8"), "keep")

    def test_output_inside_input_or_skill_tree_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_dir = root / "unpacked"
            input_dir.mkdir()
            for name, contents in entries().items():
                target = input_dir / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(contents, encoding="utf-8")
            inside_input = input_dir / "result.md"
            result = self.run_cli(input_dir, "--output-md", inside_input)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(inside_input.exists())

            inside_skill = ROOT / f".smc2-export-forbidden-{os.getpid()}.md"
            self.assertFalse(inside_skill.exists())
            try:
                skill_result = self.run_cli(input_dir, "--output-md", inside_skill)
                self.assertEqual(skill_result.returncode, 2)
                self.assertFalse(inside_skill.exists())
            finally:
                if inside_skill.exists():
                    inside_skill.unlink()

    def test_write_failure_returns_structured_error_and_cleans_temp_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "write-failure.smc2"
            output = root / "result.md"
            make_zip(archive, entries())
            stdout = io.StringIO()

            with patch.object(locate.os, "link", side_effect=PermissionError("denied")):
                with contextlib.redirect_stdout(stdout):
                    exit_code = locate.main([str(archive), "PumpLogic", "--output-md", str(output)])

            summary = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 2)
            self.assertEqual(summary["export_status"], "failed")
            self.assertFalse(output.exists())
            self.assertEqual(list(root.glob(".result.md.*.tmp")), [])

    def test_variable_view_is_readable_and_tampering_or_missing_rows_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "variables.smc2"
            mapping = entries()
            source = ('[SLWD version=1.0]\r\n_EN=Variables\r\n'
                      '+GN=VAR_INPUT\tGVT=Group\r\n'
                      '++D=BOOL\tN=Enable\tG=VAR_INPUT\tCom=允许|停止 <仅说明> `备注`\tExtraField=keep-me\r\n'
                      '+GN=VAR_OUTPUT\tGVT=Group\r\n'
                      '++D=UINT\tN=ReadyCount\tCom=完成计数\r\n')
            mapping[f"decl/{V_GUID}.xml"] = source
            make_zip(archive, mapping)
            extracted = locate.locate(archive, "PumpLogic", include_source=True)
            path = root / "readable.md"
            locate.export_markdown(extracted, archive, path)
            document = path.read_bytes().decode("utf-8")
            self.assertEqual(locate.extract_source_blocks(document)["variables"], source)
            self.assertIn('| 变量名 | 类型 | 声明组/方向 | 初值 | 地址/属性 | 原注释 |', document)
            self.assertIn('允许&#124;停止 &lt;仅说明&gt; &#96;备注&#96;', document)
            self.assertIn('ExtraField=keep-me', document)
            self.assertTrue(locate.validate_export(document, extracted)['variable_view_equal'])
            for changed in (document.replace('| ReadyCount | UINT |', '| ReadyCount | DINT |', 1),
                            '\n'.join(line for line in document.split('\n') if not line.startswith('| Enable |'))):
                with self.assertRaises(ValueError):
                    locate.validate_export(changed, extracted)

    def test_variable_values_render_as_literal_text_not_markdown(self):
        from markdown_it import MarkdownIt
        comments = ('计算 P*I*D', '[说明](https://example.com)',
                    '__保持原注释__ ~~不删除~~ ![图](image.png)',
                    r'路径 C:\temp\record 与 a_b_c',
                    '允许|停止 <仅说明> `备注` & 原值')
        for comment in comments:
            with self.subTest(comment=comment):
                source = ('[SLWD version=1.0]\n_EN=Variables\n+GN=VAR_INPUT\n'
                          '++D=REAL\tN=Gain\tCom=' + comment + '\n')
                tokens = MarkdownIt('commonmark').enable('table').parse(locate._variable_section(source))
                cells = []
                for index, token in enumerate(tokens):
                    if token.type == 'td_open':
                        inline = tokens[index + 1]
                        children = inline.children or []
                        self.assertTrue(children)
                        self.assertTrue(all(child.type == 'text' for child in children))
                        cells.append(''.join(child.content for child in children))
                self.assertEqual(len(cells), 6)
                self.assertEqual(cells[0], 'Gain')
                self.assertEqual(cells[1], 'REAL')
                self.assertEqual(cells[5], comment)

    def test_source_can_contain_document_like_markers_without_losing_raw_text(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / 'marker-code.smc2'
            source = ('(*\n<!-- plc-variable-view:start -->\n\n'
                      '<a id="validation"></a>\n<!-- plc-variable-view:end -->\n*)\n')
            mapping = entries()
            mapping[f'body/{B_GUID}.xml'] = body_xml(source)
            make_zip(archive, mapping)
            extracted = locate.locate(archive, 'PumpLogic', part='body', include_source=True)
            locate.export_markdown(extracted, archive, root / 'source.md')
            document = (root / 'source.md').read_bytes().decode('utf-8')
            self.assertEqual(locate.extract_source_blocks(document), {'body': source})

    def test_markdown_renderer_failure_prevents_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "render.smc2"
            make_zip(archive, entries())
            extracted = locate.locate(archive, "PumpLogic", include_source=True)
            fake = subprocess.CompletedProcess([], 2, "renderer unavailable", "")
            with patch.object(locate.subprocess, 'run', return_value=fake):
                with self.assertRaises(ValueError):
                    locate.export_markdown(extracted, archive, root / 'out.md')
            self.assertFalse((root / 'out.md').exists())
            self.assertEqual(list(root.glob('.out.md.*.tmp')), [])

    def test_readback_validation_detects_tampered_fenced_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "tamper.smc2"
            output = root / "result.md"
            source = "(* TAMPER_SENTINEL *)\nOutput := TRUE;\n"
            mapping = entries()
            mapping[f"body/{B_GUID}.xml"] = body_xml(source)
            make_zip(archive, mapping)
            result = self.run_cli(archive, "--part", "body", "--output-md", output)
            self.assertEqual(result.returncode, 0, result.stderr)

            document = output.read_bytes().decode("utf-8")
            self.assertEqual(locate.extract_source_blocks(document)["body"], source)
            tampered = document.replace("TAMPER_SENTINEL", "ALTERED_SENTINEL", 1)
            with self.assertRaises(ValueError):
                locate.extract_source_blocks(tampered)


if __name__ == "__main__":
    unittest.main()
