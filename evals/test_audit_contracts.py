#!/usr/bin/env python3
"""跨来源、模板与成品校验的审计回归；不依赖真实控制器。"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'evals')]
import _harness as harness
import make_manifest
import check_code_integrity as integrity


class AuditContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, text):
        path = self.root / name
        path.write_text(text, encoding='utf-8')
        return path

    def manifest(self, source):
        src = self.write('source.st', source)
        data = make_manifest.make_manifest(src, 'network')
        path = self.write('manifest.json', json.dumps(data))
        return path, data

    def test_prefix_declarations_and_initialization_remain_required(self):
        source = '// 工程：演示\n[Main]\nVAR\n xInit : BOOL;\nEND_VAR\nxInit := TRUE;\n// NETWORK 1\ny := xInit;\n// NETWORK 2\ny := FALSE;\n'
        manifest, data = self.manifest(source)
        excluded = {n for e in data['exclude'] for n in range(e['start'], e['end'] + 1)}
        self.assertFalse(excluded & {3, 4, 5, 6}, data)
        self.assertTrue({1, 2} <= excluded, data)
        doc = self.write('doc.md', '<!-- src: 7-8 -->\n```st\n// NETWORK 1\ny := xInit;\n```\n<!-- src: 9-10 -->\n```st\n// NETWORK 2\ny := FALSE;\n```\n')
        report = integrity.run(manifest, doc, False, set(), final=True)
        self.assertTrue(report.missing, vars(report))

    def test_source_template_syntax_and_per_block_binding(self):
        manifest, _ = self.manifest('// NETWORK 1\nx := 1;\n// NETWORK 2\nx := 2;\n')
        good = '<!-- src: 1-2；来源/对象：source.st -->\n```st\n// NETWORK 1\nx := 1;\n```\n<!-- src: source.st:3-4 -->\n```st\n// NETWORK 2\nx := 2;\n```\n'
        report = integrity.run(manifest, self.write('doc.md', good), False, set(), final=True)
        self.assertEqual(report.errors, 0, vars(report))
        for marker in ('', '<!-- src: wrong -->', '<!-- src: 0-2 -->', '<!-- src: 4-3 -->', '<!-- src: 3-4 garbage -->'):
            bad = good.replace('<!-- src: source.st:3-4 -->', marker)
            report = integrity.run(manifest, self.write('doc.md', bad), False, set())
            self.assertGreater(report.errors, 0, marker)

    def test_none_cannot_cover_next_unmarked_fence(self):
        from validate_handbook import main
        text = '> 文档类型：handbook\n> 深度：代码深度\n\n## 来源说明\n\n<!-- src: none -->\n```st\nx := 1; // 当前分支保存请求，撤销条件在其他写入点核对\n```\n\n```st\nx := 2; // 当前分支覆盖上次请求，后续消费者读取该结果\n```\n'
        result = harness.run(ROOT / 'scripts/validate_handbook.py', self.write('doc.md', text))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('src:', result.stdout)

    def test_long_closed_source_once_with_branch_line_references(self):
        from check_plc_comments import check_text
        lines = ['// NETWORK 1', 'IF xRequest THEN', '    CASE iStep OF', '    10:']
        notes = ['', '请求有效时才更新下面的阶段结果，入口任务未提供',
                 '按本次读到的步号选择一路动作，后续写入仍需核对', '等待分支只在步号为十时参与更新']
        for n in range(6):
            lines.append(f'        result{n} := input{n};')
            notes.append(f'保存第 {n + 1} 路本次输入供下游读取，撤销位置未提供')
        lines += ['    ELSE', '        xError := TRUE;', '    END_CASE;', 'END_IF;', '// NETWORK 2', 'xSeen := xRequest;']
        notes += ['其它步号进入异常路径，不执行上面六路更新', '异常路径置位诊断结果，清除方需补调用者证据', '', '', '', '保存请求快照供后续逻辑对照，本段没有驱动现场输出']
        manifest, _ = self.manifest('\n'.join(lines) + '\n')
        teaching = [line + (' // ' + note if note else '') for line, note in zip(lines, notes)]
        doc = ('> 文档类型：handbook | 深度：代码深度\n\n## 请求与结果\n\n'
               '<a id="whole"></a>\n<!-- src: 1-14；来源/对象：source.st -->\n```st\n' + '\n'.join(teaching[:14]) + '\n```\n'
               '逐句看：[完整源码](#whole)；L2 请求入口；L3–4 选择等待分支；'
               'L5–10 逐路保存输入，任一路未执行会留下旧值；L11–12 异常路径；L13–14 闭合上述作用域。\n'
               '<!-- src: 15-16 -->\n```st\n' + '\n'.join(teaching[14:]) + '\n```\n')
        report = integrity.run(manifest, self.write('long.md', doc), False, set(), final=True)
        self.assertEqual(report.errors, 0, vars(report))
        self.assertFalse(check_text(doc)['errors'], check_text(doc)['errors'])
        for note in filter(None, notes):
            bad = doc.replace(' // ' + note, '')
            self.assertTrue(check_text(bad)['errors'], '不能以逐句正文豁免执行行注释：' + note)
        duplicate = doc + '<!-- src: 1-14 -->\n```st\n' + '\n'.join(teaching[:14]) + '\n```\n'
        self.assertTrue(integrity.run(manifest, self.write('dup.md', duplicate), False, set()).duplicate)
        rules = (ROOT / 'references/code-reading.md').read_text()
        self.assertNotIn('再逐个分支讲，不整段贴', rules, '规范仍禁止保真长结构的合法交付')
        self.assertNotIn('只贴该分支代码（带必要的 CASE 头/结束说明）', rules)

    def test_recommended_st_fb_numbered_topics_pass_end_to_end(self):
        import re
        from check_plc_comments import check_text
        for template, combo in [('template-st-xml-framework.md', 'ST'), ('template-mfb-xml.md', 'FB')]:
            source = '// NETWORK 1\nxEnable := xRequest;\n// NETWORK 2\nxOutput := xEnable;\n'
            manifest, _ = self.manifest(source)
            headings = re.findall(r'^## .+$', (ROOT / 'references' / template).read_text(), re.M)
            doc = ('# 请求与输出\n> 文档类型：handbook | 深度：代码深度\n'
                   f'> 模板组合：HBK@2.2 + {combo}@2.2\n\n## 目录\n\n')
            doc += '\n'.join(f'- [{h[3:]}](#topic{n})' for n, h in enumerate(headings)) + '\n'
            details = [
                '已确认：请求先刷新本地使能，再由第二网络复制到输出；任务周期和现场接线未提供。',
                'xRequest 来自调用者；xEnable 是中间结果；xOutput 供下游读取。未提供其他写入点，不能断言最终物理输出。',
                '请求为真时两段结果为真；请求撤销时本次调用的两段赋值均写假。调用跳过时是否保持需查平台与任务配置。',
            ]
            for n, heading in enumerate(headings):
                heading = re.sub(r'<[^>]+>', '请求与结果', heading)
                doc += f'\n<a id="topic{n}"></a>\n{heading}\n\n{details[n % 3]}\n'
                if combo == 'FB' and '执行状态与异常' in heading:
                    doc += ('\n| 当前状态 | 转移条件 | 下一状态 | 外部可见结果 | 证据等级 |\n'
                            '|---|---|---|---|---|\n'
                            '| 请求未到达 | xRequest 为真 | 请求有效 | 可见源码复制请求到使能及结果 | 已确认 |\n')
            doc += ('\n<!-- src: 1-2；来源/对象：source.st -->\n```st\n// NETWORK 1\n'
                    'xEnable := xRequest; // 下个网络本次读取刚刷新的请求，调用跳过时行为需查平台\n```\n'
                    '<!-- src: 3-4 -->\n```st\n// NETWORK 2\n'
                    'xOutput := xEnable; // 本网络将上段结果交给下游读取，物理输出归属未提供\n```\n')
            path = self.write('topic.md', doc)
            result = harness.run(ROOT / 'scripts/validate_handbook.py', path, '--original-source')
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertFalse(check_text(doc)['errors'])
            self.assertEqual(integrity.run(manifest, path, False, set(), final=True).errors, 0)
            # Final delivery exercises the current-document review contract too.
            import hashlib
            report = check_text(doc)
            review = {'document_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                      'reviewer': 'synthetic fixture author', 'blocks': [
                          {'fence_line': b['line'], 'code_sha256': b['sha256'], 'status': 'reviewed',
                           'covered_lines': b['required_lines'], 'evidence': 'temporary source.st plus ordered networks',
                           'rationale': 'only assignment data flow is asserted; task, wiring and other writers remain unknown',
                           'issues': []} for b in report['blocks']]}
            receipt = self.write('review.json', json.dumps(review))
            result = harness.run(ROOT / 'scripts/validate_handbook.py', path, '--final', '--original-source', '--comment-review', receipt)
            self.assertEqual(result.returncode, 0, result.stdout)
            bad = doc.replace('<!-- src: 3-4 -->', '')
            result = harness.run(ROOT / 'scripts/validate_handbook.py', self.write('missing-source.md', bad), '--original-source')
            self.assertEqual(result.returncode, 1, result.stdout)
            bad = doc.replace('xOutput := xEnable;', 'xOutput := FALSE;')
            self.assertTrue(integrity.run(manifest, self.write('altered.md', bad), False, set()).altered)


    def test_final_unfinished_status_checked_in_every_chapter(self):
        base = '> 文档类型：handbook | 深度：流程深度\n\n'
        for title in ('四、工位地图与段分类', '五、模块详解', '保护边界', '范围外缺口'):
            # Topic sections avoid unrelated HBK anchor requirements.
            doc = base + f'## {title}\n\n| 对象 | 状态 |\n|---|---|\n| FB_A | 受保护 |\n'
            result = harness.run(ROOT / 'scripts/validate_handbook.py', self.write('status.md', doc), '--final')
            self.assertIn('最终交付仍有未完成覆盖状态', result.stdout, result.stdout)
        for line in ('> 状态：受保护', '> 本体可见性：部分', '> 项目源码覆盖：部分覆盖', '> 未覆盖：报警块（受保护）', '> 尚未覆盖：网络 3 至 8', '> 本次交付：未完成'):
            result = harness.run(ROOT / 'scripts/validate_handbook.py', self.write('meta.md', base + line + '\n\n## 事实\n\n仅记录可见接口，内部范围缺失。\n'), '--final')
            self.assertEqual(result.returncode, 1, result.stdout)

    def test_local_delivery_and_project_coverage_are_independent(self):
        base = ('> 文档类型：handbook | 深度：流程深度\n> 交付范围：局部\n'
                '> 本次覆盖：FB_A 的可见接口及调用者\n> 本次交付：完成\n'
                '> 项目源码覆盖：部分覆盖\n> 用户理解：未自测\n\n')
        doc = (base + '## 接口与调用\n\n已确认调用者提供请求，结果由后续网络读取；本体不可读，不能说明内部保持与复位。\n'
               '## 范围外缺口\n\n| 对象 | 状态 |\n|---|---|\n| FB_A 本体 | 受保护 |\n')
        result = harness.run(ROOT / 'scripts/validate_handbook.py', self.write('local.md', doc), '--final')
        self.assertEqual(result.returncode, 0, result.stdout)
        result = harness.run(ROOT / 'scripts/validate_handbook.py', self.write('unverifiable.md', doc.replace('项目源码覆盖：部分覆盖', '项目源码覆盖：无法对账')), '--final')
        self.assertEqual(result.returncode, 0, result.stdout)
        for bad in (doc.replace('项目源码覆盖：部分覆盖', '项目源码覆盖：全覆盖'),
                    doc.replace('## 范围外缺口', '## 本次讲解'),
                    doc.replace('> 本次覆盖：FB_A 的可见接口及调用者\n', '')):
            result = harness.run(ROOT / 'scripts/validate_handbook.py', self.write('bad.md', bad), '--final')
            self.assertEqual(result.returncode, 1, result.stdout)

    def test_readonly_facts_are_allowed_but_operating_instructions_refused(self):
        from validate_handbook import check_safety_boundary
        good = [
            '程序在配方下载完成后置位 xRecipeReady，此处只解释现有逻辑。',
            '| 互锁 | 手动模式强制 `xManualClamp`，`iStep` 仍为 20 | 本段仍置位输出 |',
            '可下载本手册供离线阅读。',
            '现有程序在维护模式将强制标志写入诊断字，该行为并不证明现场安全。',
            '下载指令在通信任务中提交配方，具体平台语义待核对。',
            '请解释强制输出 Y0 的现有逻辑，不进行现场操作。',
            '禁止修改 PLC 程序；不下载、不强制 I/O、不旁路安全。',
        ]
        bad = [
            '请强制输出 Y0 观察设备动作。', '将 Y0 强制为 ON。',
            '请使用下载功能将程序写入控制器。', '请强制标志位以绕过当前条件。',
            '建议下载 PLC 程序再观察结果。', '请下载至控制器。',
            '强制 Y0 后查看动作。', '先禁止强制 I/O，然后可以强制 Y0。',
            '不得强制 I/O，但是建议旁路安全回路。',
            '下一步：在线改参确认延时。', '操作员应强制 Y0。',
            '可强制 Y0 验证。', '请在手动模式强制 Y0。', '为观察动作，强制 Y0。',
        ]
        for sentence in good:
            errors = []
            check_safety_boundary(sentence, errors)
            self.assertFalse(errors, (sentence, errors))
        for sentence in bad:
            errors = []
            check_safety_boundary(sentence, errors)
            self.assertTrue(errors, sentence)

    def test_survey_masks_literals_comments_and_finds_inline_writes(self):
        from survey_program import scan, render
        text = ("// NETWORK 1\n// SET(yFake, TRUE); FakeCall(X999);\n"
                "(* yGhost := TRUE; Nested(X888); (* OUT(Y666); *) *)\n"
                "s := 'FakeCall(X777) // SET(Y555, TRUE)';\n"
                't := "OtherCall(X444)";\n'
                "IF flag THEN yRun := TRUE; z := 1; END_IF;\n"
                "(* comment begins\nSET(Y333, TRUE);\n*)\n"
                "// NETWORK 2\nyRun := FALSE; z := 2;\nRealCall(X1);\n")
        data = scan(self.write('scan.st', text), 'network', 20)
        self.assertNotIn('YFAKE', data['writes'])
        self.assertNotIn('YGHOST', data['writes'])
        self.assertEqual(data['addresses'].get('X'), ['X1'])
        self.assertNotIn('FakeCall', data['calls'])
        self.assertEqual(data['calls']['RealCall'], 1)
        self.assertEqual(data['cross_unit_writes']['YRUN'], ['POU.N1', 'POU.N2'])
        self.assertEqual(data['cross_unit_writes']['Z'], ['POU.N1', 'POU.N2'])
        self.assertEqual([site['line'] for site in data['write_sites'] if site['target'] == 'yRun'], [6, 11])
        self.assertEqual(data['classification'], '候选统计')
        self.assertTrue(data['syntax_limits'])
        self.assertIn('候选统计', render(data, 20))

    def test_instruction_semantics_require_platform_evidence(self):
        text = (ROOT / 'references/code-reading.md').read_text()
        row = next(line for line in text.splitlines() if '比较/传送（CMP/MOV）' in line)
        self.assertNotIn('只在一个扫描周期执行一次', row)
        for topic in ('平台', '指令形式', '条件/使能', '执行时机'):
            self.assertIn(topic, text[text.index('## 指令语义'):text.index('## 必须先识别')])

    def test_shared_fences_pascal_quote_and_list_containers(self):
        from markdown_fences import parse_fences
        from check_plc_comments import check_text
        from validate_st_rendering import check
        source = 'xResult := xRequest; // 当前请求供下游读取，撤销时由本段同步刷新结果'
        variants = [f'```pascal\n{source}\n```\n',
                    f'> ```st\n> {source}\n> ```\n',
                    f'- 教学段\n\n  ```st\n  {source}\n  ```\n',
                    f'- ```st\n  {source}\n  ```\n',
                    f'1. 教学段\n\n   ~~~pascal\n   {source}\n   ~~~\n']
        for doc in variants:
            errors, count = check(self.write('fence.md', doc))
            self.assertEqual(count, 1, doc)
            self.assertFalse(errors, errors)
            blocks = parse_fences(doc)
            self.assertEqual(blocks[0]['source_lines'], [source])
            self.assertFalse(check_text(doc)['errors'], check_text(doc)['errors'])
        errors, count = check(self.write('unclosed.md', '```pascal\nx := 1;\n'))
        self.assertEqual(count, 1)
        self.assertTrue(errors)

    def test_mermaid_tilde_and_nested_example_headings_share_body_view(self):
        from check_content_consistency import check as consistent
        from check_document_layout import check as layout
        text = ('## 步序\n\n| 步 | 动作 |\n|---|---|\n| 10 | 等待 |\n| 20 | 执行 |\n\n'
                '~~~mermaid\nstateDiagram-v2\n步10_等待 --> 步99_错误\n~~~\n')
        self.assertTrue(any('步99' in issue for issue in consistent(self.write('steps.md', text))))
        example = ('# 教学\n\n## 一、真实章节\n\n下方为示例文字，标题不进入正文结构。\n\n'
                   '````markdown\n## 一、示例\n\n```st\nx := 1;\n```\n\n## 一、第二个示例\n````\n')
        self.assertFalse(layout(self.write('headings.md', example))[0])
        result = harness.run(ROOT / 'scripts/check_markdown_format.py', self.write('headings.md', example))
        self.assertNotIn('章节编号重复', result.stdout)
        doc = ('> 文档类型：handbook | 深度：流程深度\n\n## 事实边界\n\n仅记录当前可见调用，周期未知。\n\n'
               + example[example.index('````markdown'):])
        result = harness.run(ROOT / 'scripts/validate_handbook.py', self.write('handbook.md', doc))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_input_types_use_explicit_material_names(self):
        import re
        docs = [ROOT / 'SKILL.md', *sorted((ROOT / 'references').glob('*.md')), ROOT / 'evals/cases.md']
        dangling = [(path.name, match.group()) for path in docs
                    for match in re.finditer(r'A/B/C/D|C/D|输入形态 C', path.read_text())]
        self.assertFalse(dangling, dangling)

    def test_unknown_prefix_with_comments_is_one_preserved_context(self):
        _, data = self.manifest('[Main]\nVAR\n // 声明注释\n x : BOOL;\nEND_VAR\n\nx := TRUE;\n// NETWORK 1\ny := x;\n// NETWORK 2\ny := FALSE;\n')
        units = [u for u in data['units'] if u['kind'] == 'unclassified']
        self.assertEqual([(u['start'], u['end']) for u in units], [(2, 7)])

    def test_unsupported_container_combinations_cannot_be_zero_block_green(self):
        from validate_st_rendering import check
        from check_plc_comments import check_text
        for doc in ('- > ```st\n  > x := 1;\n  > ```\n',
                    '- - ```st\n    x := 1;\n    ```\n',
                    '- 教学\n\n\t```st\n\tx := 1;\n\t```\n'):
            errors, count = check(self.write('containers.md', doc))
            self.assertTrue(errors or count == 1, (errors, count, doc))
            self.assertTrue(any('容器' in message for message in check_text(doc)['errors']), '不支持的容器必须明确诊断')

    def test_safety_instruction_in_text_fence_still_refused(self):
        doc = '> 文档类型：handbook | 深度：流程深度\n\n## 操作说明\n\n```text\n请强制输出 Y0 观察动作。\n```\n'
        result = harness.run(ROOT / 'scripts/validate_handbook.py', self.write('unsafe.md', doc))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('只读安全边界', result.stdout)

    def test_user_success_section_is_required_and_not_a_strict_violation(self):
        import validate_skill
        raw = (ROOT / 'SKILL.md').read_text()
        errors, warnings = [], []
        validate_skill.strict_checks(ROOT, raw, errors, warnings)
        self.assertFalse(errors, errors)
        errors, warnings = [], []
        raw = raw.replace('## 读者与成功标准（Reader & Success Test）', '成功标准')
        validate_skill.strict_checks(ROOT, raw, errors, warnings)
        self.assertTrue(errors, '用户成功标准仍须被入口结构契约保留')

    def test_source_binding_in_quote_and_list_still_checks_exact_lines(self):
        manifest, _ = self.manifest('// NETWORK 1\nx := 1;\n// NETWORK 2\nx := 2;\n')
        plain = '<!-- src: 1-2 -->\n```st\n// NETWORK 1\nx := 1;\n```\n'
        variants = ['\n'.join('> ' + line for line in plain.splitlines()) + '\n',
                    '- ' + plain.splitlines()[0] + '\n' + '\n'.join('  ' + line for line in plain.splitlines()[1:]) + '\n']
        tail = '<!-- src: 3-4 -->\n```st\n// NETWORK 2\nx := 2;\n```\n'
        for variant in variants:
            path = self.write('container-source.md', variant + '\n' + tail)
            report = integrity.run(manifest, path, False, set(), final=True)
            self.assertEqual(report.errors, 0, vars(report))
            bad = self.write('container-source.md', (variant + '\n' + tail).replace('x := 1;', 'x := 9;'))
            self.assertTrue(integrity.run(manifest, bad, False, set()).altered)

    def test_layout_accepts_shared_plc_language_aliases(self):
        from check_document_layout import check
        for lang in ('scl', 'structured-text', 'iecst', 'FB'):
            errors, warnings = check(self.write('alias.md', f'```{lang}\nx := 1;\n```\n'))
            self.assertFalse(errors, errors)
            self.assertFalse(any('语言' in warning for warning in warnings), warnings)

    def test_survey_block_comment_cannot_invent_network_boundaries(self):
        from survey_program import scan
        text = '// NETWORK 1\nx := 1;\n(* header example\n// NETWORK 999\n[FakePOU]\n*)\nx := 2;\n// NETWORK 2\nx := 3;\n'
        data = scan(self.write('boundaries.st', text), 'network', 20)
        self.assertEqual(data['units'], 2, data)
        self.assertEqual(data['cross_unit_writes']['X'], ['POU.N1', 'POU.N2'])


if __name__ == '__main__':
    unittest.main()
