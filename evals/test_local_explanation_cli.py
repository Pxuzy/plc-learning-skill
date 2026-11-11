#!/usr/bin/env python3
"""真实 subprocess 检查 B 默认原码、精确字符和覆盖映射/待审清单。"""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from test_local_explanation_contract import ROOT, VALID, SOURCE, filled_skeleton

CLI = ROOT / 'scripts/check_local_explanation.py'


def invoke(text=VALID, source=SOURCE):
    # 本文件校验的是“原码”模式（模式 B）：源码逐字符保真、不追加 AI 尾注，
    # 因此显式走 --original-source；默认逐行注释契约由 test_default_annotations 覆盖。
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp)/'local.md'; src = Path(tmp)/'input.st'
        doc.write_bytes(text.encode('utf-8')); src.write_bytes(source.encode('utf-8'))
        return subprocess.run([sys.executable,'-B',str(CLI),str(doc),'--source',str(src),'--original-source'],
                              env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}, capture_output=True, text=True)


class LocalCliTests(unittest.TestCase):
    def reject(self, text, message, source=SOURCE):
        result = invoke(text,source)
        self.assertEqual(result.returncode,1,result.stdout+result.stderr)
        self.assertIn('ERROR',result.stdout)
        self.assertIn(message,result.stdout)

    def test_explicit_ai_tails_preserve_source_prefix_and_author_comments(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp)/'note.md'; src = Path(tmp)/'input.st'
            source = SOURCE.replace('IF xFault THEN', 'IF xFault THEN // 作者 // AI: 原标记')
            annotated = ''.join(line.rstrip('\n')+' // AI: 简短业务说明\n' for line in source.splitlines(keepends=True))
            text = VALID.replace(SOURCE, annotated)
            src.write_text(source); doc.write_text(text)
            cmd = [sys.executable, '-B', str(CLI), str(doc), '--source', str(src), '--allow-ai-tails']
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            for bad in (text.replace('xRun := FALSE;', 'xRun := TRUE;', 1),
                        text.replace('// 作者 // AI: 原标记', '// 作者', 1),
                        text.replace(' // AI: 简短业务说明', ' // AI: ', 1),
                        text.replace(annotated, annotated.replace('\n', '\r\n'))):
                doc.write_text(bad)
                self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)

    def test_original_mode_b_passes_without_handbook_or_new_inline_comments(self):
        self.assertTrue(CLI.is_file(),'模式 B 缺少专用 CLI 入口')
        result = invoke()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('结构/源码检查通过',result.stdout)
        self.assertIn('待审',result.stdout)
        self.assertNotIn('语义通过',result.stdout)

    def test_preface_missing_field_and_terminal_rejected(self):
        for text, message in (('我先讲解。\n'+VALID,'正式稿'),
                              (VALID.replace('**代码职责**','**别名**'),'代码职责'),
                              (VALID.replace('<!-- 本段已完 -->',''),'结束')):
            with self.subTest(message=message): self.reject(text,message)

    def test_blank_whitespace_and_original_comments_cannot_be_rewritten(self):
        self.reject(VALID.replace('    xRun := FALSE;',' xRun := FALSE;',1),'源码')
        source = SOURCE.replace('IF xFault THEN','IF xFault THEN // 原注释：保留')
        doc = VALID.replace(SOURCE,source)
        self.assertEqual(invoke(doc,source).returncode,0)
        self.reject(doc.replace(' // 原注释：保留',''), '源码', source)

    def test_repeated_lines_are_not_proven_by_substring_presence(self):
        source = SOURCE.replace('xReady := xPermit AND NOT xFault;', 'xReady := xPermit AND NOT xFault;\nxReady := xPermit AND NOT xFault;')
        doc = VALID.replace(SOURCE,source).replace('L7-L7','L7-L8')
        self.assertEqual(invoke(doc,source).returncode,0)
        self.reject(doc.replace('xReady := xPermit AND NOT xFault;\nxReady := xPermit AND NOT xFault;', 'xReady := xPermit AND NOT xFault;'), '源码',source)

    def test_trailing_newline_contract_is_explicit_no_strip(self):
        self.assertEqual(invoke().returncode,0)
        self.reject(VALID,'源码', SOURCE[:-1])
        doc = VALID.replace('END_IF;\nxReady := xPermit AND NOT xFault;\n```',
                            'END_IF;\nxReady := xPermit AND NOT xFault;\n```\n<!-- source-eof: none -->')
        self.assertEqual(invoke(doc,SOURCE[:-1]).returncode,0)
        self.reject(doc,'源码',SOURCE)
        self.reject(VALID,'源码',SOURCE+'\n')
        self.reject(VALID,'源码',SOURCE.replace('\n','\r\n'))
        crlf_doc=VALID.replace(SOURCE,SOURCE.replace('\n','\r\n'))
        self.assertEqual(invoke(crlf_doc,SOURCE.replace('\n','\r\n')).returncode,0)

    def test_source_eof_marker_allows_only_its_own_line_trailing_whitespace(self):
        doc = VALID.replace('END_IF;\nxReady := xPermit AND NOT xFault;\n```',
                            'END_IF;\nxReady := xPermit AND NOT xFault;\n```\n<!-- source-eof: none --> \t')
        result = invoke(doc, SOURCE[:-1])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        changed_source = SOURCE[:-1].replace('xReady :=', 'xReady := ', 1)
        self.reject(doc, '源码', changed_source)

    def test_separate_fences_join_in_order_without_whitespace_normalization(self):
        doc = VALID.replace('IF xFault THEN','```\n\n```st\nIF xFault THEN',1)
        self.assertEqual(invoke(doc).returncode,0)
        self.reject(doc.replace('```st\nIF xFault THEN','```st\n IF xFault THEN',1),'源码')

    def test_execution_unit_missing_both_explanation_and_unreviewed_list_rejected(self):
        # 删除对应正文而非只删关键词，三项各独立；源码仍完整。
        for line_range in ('L1-L1','L4-L6','L7-L7'):
            bad = re.sub(r'<!-- explanation: '+line_range+r' -->\n.*?\n\n','',VALID,count=1,flags=re.S)
            self.assertNotEqual(bad,VALID)
            with self.subTest(line_range=line_range): self.reject(bad,'覆盖')

    def test_explicit_unreviewed_list_keeps_pending_not_semantic_pass(self):
        doc = re.sub(r'<!-- explanation: L7-L7 -->\n.*?\n\n','<!-- unreviewed: L7-L7 -->\n末行赋值的作用与后果尚待人工解释核对。\n\n',VALID,count=1,flags=re.S)
        result = invoke(doc)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('L7',result.stdout); self.assertIn('未审',result.stdout)
        self.assertNotIn('语义通过',result.stdout)

    def test_marker_without_explanation_cannot_supply_coverage(self):
        doc = re.sub(r'(?s)(<!-- explanation: L7-L7 -->)\n.*?\n\n',r'\1\n\n',VALID,count=1)
        self.reject(doc,'覆盖')

    def test_header_metadata_and_source_section_are_checked(self):
        for old in ('> 工程：虚构教学片段，非现场工程\n','> 讲解深度：零基础局部深讲\n','> 模块编号：M01 起按源码逻辑顺序\n'):
            with self.subTest(old=old): self.reject(VALID.replace(old,''),'元信息')
        self.reject(VALID.replace('## 整体功能与关键变量 🧭','# 整体功能与关键变量 🧭'),'H1')
        self.reject(VALID.replace('```st','```text',1),'源码')

    def test_both_filled_templates_use_same_real_cli(self):
        for name in ('local-code-explanation.md','one-page-prompt.md'):
            doc=filled_skeleton(ROOT/'references'/name)
            result=invoke(doc)
            with self.subTest(name=name): self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_beginner_requires_coverage_and_truthful_reader_metadata(self):
        ordinary = VALID.replace('> 讲解深度：零基础局部深讲', '> 讲解深度：局部深讲')
        ordinary = ordinary.replace('> 模块编号：', '> 读者：工程师\n> 模块编号：')
        missing = re.sub(r'(?m)^<!-- explanation: L7-L7 -->\n.*?\n\n', '', ordinary, count=1, flags=re.S)
        self.assertEqual(invoke(missing).returncode, 0, invoke(missing).stdout)
        beginner = ordinary.replace('> 读者：工程师', '> 读者：初学者')
        missing = re.sub(r'(?m)^<!-- explanation: L7-L7 -->\n.*?\n\n', '', beginner, count=1, flags=re.S)
        self.reject(missing, '覆盖')
        shallow = VALID.replace('> 讲解深度：零基础局部深讲', '> 讲解深度：局部深讲')
        shallow = re.sub(r'(?m)^<!-- explanation: L7-L7 -->\n.*?\n\n', '', shallow, count=1, flags=re.S)
        result = invoke(shallow)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('未启用零基础逐范围覆盖', result.stdout)

    def test_coverage_body_may_start_with_bold_lead_but_not_contract_field_or_empty(self):
        good = VALID.replace('L7 在选择结构之后', '**末行**：L7 在选择结构之后', 1)
        self.assertEqual(invoke(good).returncode, 0, invoke(good).stdout)
        for body in ('**关键逻辑**：借用下一必填字段。', ''):
            bad = re.sub(r'(?ms)(<!-- explanation: L7-L7 -->\n).*?(?=\n\n\*\*关键逻辑\*\*)',
                         lambda m: m[1] + body, VALID, count=1)
            self.reject(bad, '覆盖')

    def test_ordinary_reader_still_rejects_forged_or_bare_coverage_markers(self):
        ordinary=VALID.replace('零基础局部深讲','局部深讲')
        cases = (('<!-- explanation: L999-L999 -->\n实际文字。', '覆盖'),
                 ('<!-- explanation: L7-L7 -->\n**末行**', '覆盖'),
                 ('<!-- explanation: L7-L7 -->\n**末行**：\n**关键逻辑**：借用字段正文。', '关键逻辑'),
                 ('<!-- explanation: L7-L7 -->\n#### 只有标题', '覆盖'),
                 ('<!-- explanation: L7-? -->\n实际文字。', '覆盖'),
                 ('<!-- explanation: L7-L7 -->\n<!-- explanation: L7-L7 -->\n实际文字。', '覆盖'))
        for replacement, reason in cases:
            bad=re.sub(r'(?ms)<!-- explanation: L7-L7 -->\n.*?(?=\n\n\*\*关键逻辑\*\*)',
                       lambda m:replacement,ordinary,count=1)
            with self.subTest(replacement=replacement):self.reject(bad,reason)
        misplaced=ordinary.replace('<!-- src: none', '<!-- explanation: L7-L7 -->\n此处不是第三部分。\n\n<!-- src: none',1)
        self.reject(misplaced,'覆盖')

    def test_local_repair_loop_retains_raw_and_never_delivers_failed_attempt(self):
        raw = VALID.replace('**代码职责**','**错误标签**')
        attempts=[raw,raw,VALID]; delivered=None
        for attempt in attempts[:3]:
            result=invoke(attempt)
            if result.returncode==0:
                delivered=attempt;break
        self.assertEqual(attempts[0],raw)
        self.assertEqual(delivered,VALID)
        self.assertTrue(all(invoke(raw).returncode!=0 for _ in range(3)))
        self.assertIn(SOURCE,delivered)


if __name__=='__main__': unittest.main(verbosity=2)
