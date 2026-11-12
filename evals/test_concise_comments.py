#!/usr/bin/env python3
"""Concise business comments keep coverage without per-unit presentation labels."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import check_plc_comments as checker


def report(code):
    return checker.check_text('```st\n' + code + '\n```\n')


def test_complete_single_action_if_accepts_one_business_comment():
    for code in (
        'IF r_TrigStepDone.Q THEN iStepAll:=2; END_IF; // 检测到本步完成，标记进入下一工序阶段',
        'IF xPermit THEN astStation[i].xStart:=TRUE; END_IF; // 获得本站许可后向机台发出启动请求',
        'if xPermit then a[i + 1].xStart := TRUE; end_if; // 为下一工位发布启动请求',
    ):
        result = report(code)
        assert not result['errors'], result['errors']
        assert result['blocks'][0]['covered'] == result['blocks'][0]['units'] == 2


def test_sharing_does_not_cover_unclosed_nested_or_multiple_actions():
    for code in (
        'IF x THEN y:=TRUE; // 本次向机台发布启动请求',
        'IF x THEN y:=TRUE; z:=FALSE; END_IF; // 本次向机台发布启动请求',
        'IF x THEN IF y THEN z:=TRUE; END_IF; END_IF; // 本次向机台发布启动请求',
        'x:=TRUE; y:=FALSE; // 本次向机台发布启动请求',
        'IF x THEN fb(IN:=y); END_IF; // 本次向机台发布启动请求',
    ):
        assert report(code)['errors'], code


def test_single_action_still_rejects_missing_or_low_value_comments():
    for note in ('', ' // 执行当前操作', ' // 将 y 赋值为 TRUE', ' // 未知'):
        assert report('IF x THEN y:=TRUE; END_IF;' + note)['errors'], note


def test_plain_append_checks_the_new_comment_without_required_prefix():
    accepted = report('x:=TRUE; // 原有说明 // 为当前工位发布新的启动请求')
    assert not accepted['errors'], accepted['errors']
    for note in ('执行当前操作', '未知', '将 x 赋值为 TRUE'):
        assert report('x:=TRUE; // 原有说明 // ' + note)['errors'], note
        assert report('x:=TRUE; // 原有说明 // 教学补充：' + note)['errors'], note


def test_shared_note_does_not_hide_repetition_on_other_lines():
    note = ' // 获得本站许可后向机台发出启动请求'
    code = 'IF x THEN a:=TRUE; END_IF;' + note + '\nIF y THEN b:=TRUE; END_IF;' + note
    assert any('重复粘贴' in error for error in report(code)['errors'])
    code = 'IF x THEN a:=TRUE; END_IF;' + note
    repeated = checker.check_text('```st\n' + code + '\n```\n\n```st\n' + code + '\n```\n')
    assert not repeated['errors'], repeated['errors']


def test_numbered_notes_and_urls_remain_supported():
    result = report('x:=TRUE; y:=FALSE; // 原有说明 // 单元1：发布本站启动请求 | 单元2：撤销上次完成标记')
    assert not result['errors'], result['errors']
    note = '本站请求的协议定义见 https://example.invalid/plc'
    assert checker.comment_payload(note) == note


def test_ai_prefix_is_not_a_way_to_hide_empty_or_low_value_notes():
    for note in ('AI:', 'AI: 条件判断开始', 'AI: 未知', 'AI: 将 x 赋值为 TRUE'):
        assert report('IF x THEN y:=TRUE; END_IF; // ' + note)['errors'], note


def test_condition_ai_gate_covers_if_elsif_and_continuations():
    raw = '```st\nIF xReady // AI: 检查当前入口许可\n AND NOT xHold THEN // AI: 暂停标志会阻止当前写入路径\n y:=TRUE; // AI: 发布本段请求\nELSIF xReset THEN // AI: 仅前述条件未选中时检查复位请求\n y:=FALSE; // AI: 撤销本段请求\nELSE // AI: 两个入口均不满足时走保底路径\n y:=FALSE; // AI: 保底路径撤销本段结果\nEND_IF;\n```\n'
    assert not checker.check_condition_ai(raw)
    for original in ('IF xReady // AI: 检查当前入口许可',
                     ' AND NOT xHold THEN // AI: 暂停标志会阻止当前写入路径',
                     'ELSIF xReset THEN // AI: 仅前述条件未选中时检查复位请求',
                     'ELSE // AI: 两个入口均不满足时走保底路径'):
        broken = raw.replace(original, original.split(' // AI:')[0])
        assert broken != raw
        assert checker.check_condition_ai(broken), original


def test_condition_gate_ignores_strings_comments_and_graphics():
    raw = '```st\nmessage := \'IF x THEN // AI:\';\n// IF x THEN\n(* ELSIF x THEN *)\nEND_IF;\n```\n```lad\nIF x THEN\n```\n'
    assert not checker.check_condition_ai(raw)
    raw = '```st\nIF x THEN // 原作者说明 // AI: 检查该入口允许标志\nEND_IF;\n```\n'
    assert not checker.check_condition_ai(raw)
    assert checker.check_condition_ai(raw.replace(' // AI: 检查该入口允许标志', ''))


def test_single_line_if_ai_note_and_newest_payload_are_checked():
    raw = '```st\nIF x THEN y:=TRUE; END_IF; // AI: 入口允许时发布本段请求\n```\n'
    assert not checker.check_condition_ai(raw)
    assert not checker.check_text(raw)['errors']
    bad = raw.replace('入口允许时发布本段请求', '条件判断开始')
    assert checker.check_condition_ai(bad)
    assert checker.check_text(bad)['errors']
    assert checker.low_value('作者说明 // AI: 未知', 'IF x THEN')


def test_condition_gate_requires_line_comment_not_block_or_literal_marker():
    for code in ('IF x THEN (* AI: 检查该入口的允许标志 *)',
                 "IF x = ' // AI: 值' THEN", 'IF x THEN // AI:'):
        assert checker.check_condition_ai('```st\n'+code+'\nEND_IF;\n```\n'), code


def test_condition_cli_rejects_missing_tail_and_accepts_annotated_sample():
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'sample.md'
        good = '```st\nIF x THEN // AI: 检查本段入口许可\n y:=TRUE; // AI: 发布本段请求\nEND_IF; // AI: 判断收束，后续逻辑读取本段结果\n```\n'
        command = [sys.executable, '-B', str(Path(__file__).resolve().parents[1] / 'scripts/check_plc_comments.py'), str(path), '--require-condition-ai', '--json']
        path.write_text(good, encoding='utf-8')
        result = subprocess.run(command, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        path.write_text(good.replace(' // AI: 检查本段入口许可', ''), encoding='utf-8')
        result = subprocess.run(command, capture_output=True, text=True)
        assert result.returncode == 1 and '条件判断行' in result.stdout, result.stdout


def test_condition_gate_does_not_require_note_on_pure_closing_paren():
    raw = ('```st\n'
           'IF (xReady // AI: 检查本段入口许可\n'
           '   AND NOT xHold // AI: 暂停标志会阻止当前写入路径\n'
           '   )\n'
           'THEN // AI: 两项均成立才进入本段\n'
           ' y:=TRUE; // AI: 发布本段请求\n'
           'END_IF;\n'
           '```\n')
    assert not checker.check_condition_ai(raw), checker.check_condition_ai(raw)
    result = checker.check_text(raw)
    assert not result['errors'], result['errors']
    assert 4 in result['blocks'][0]['closure_lines'], result['blocks'][0]['closure_lines']
    broken = raw.replace('THEN // AI: 两项均成立才进入本段', 'THEN')
    assert any('L5' in error for error in checker.check_condition_ai(broken))


def test_condition_gate_checks_ai_segment_before_later_fragments():
    for note in ('AI: 未知 // 作者：入口许可',
                 'AI: 条件判断开始 // 见上',
                 'AI: 将 x 赋值为 TRUE // 作者备注'):
        raw = '```st\nIF x THEN y:=TRUE; END_IF; // ' + note + '\n```\n'
        assert checker.check_condition_ai(raw), note
    ok = '```st\nIF x THEN y:=TRUE; END_IF; // AI: 入口许可成立时发布本段请求 // 作者备注\n```\n'
    assert not checker.check_condition_ai(ok), checker.check_condition_ai(ok)


def test_case_else_is_not_treated_as_if_condition():
    raw = ('```st\nCASE nMode OF // AI: 按模式选择处理路径\n'
           ' 1: x:=1; // AI: 模式一写入固定结果\n'
           ' ELSE\n'
           ' x:=2; // AI: 默认模式写入保底结果\n'
           'END_CASE;\n```\n')
    assert not checker.check_condition_ai(raw), checker.check_condition_ai(raw)
    if_else = ('```st\nIF xReady THEN // AI: 入口许可成立才进入\n'
               ' y:=1; // AI: 许可路径发布结果\n'
               'ELSE\n'
               ' y:=2; // AI: 许可不成立时走保底\nEND_IF;\n```\n')
    assert any('L4' in error for error in checker.check_condition_ai(if_else)), checker.check_condition_ai(if_else)
    nested = ('```st\nIF xReady THEN // AI: 入口许可成立才进入\n'
              ' CASE nMode OF\n  1: x:=1; // AI: 模式一写入固定结果\n'
              '  ELSE\n   x:=2; // AI: 默认模式写入保底结果\n  END_CASE;\n'
              'ELSE // AI: 入口许可不成立时走保底\n y:=3; // AI: 保底路径发布结果\nEND_IF;\n```\n')
    assert not checker.check_condition_ai(nested), checker.check_condition_ai(nested)


def test_condition_gate_covers_st_in_alias_fences():
    for lang in ('plc', 'iec', 'fb'):
        raw = '```' + lang + '\nIF x THEN\n y:=TRUE;\nEND_IF;\n```\n'
        assert checker.check_condition_ai(raw), lang
        good = ('```' + lang + '\nIF x THEN // AI: 检查本段入口许可\n'
                ' y:=TRUE; // AI: 发布本段请求\nEND_IF;\n```\n')
        assert not checker.check_condition_ai(good), (lang, checker.check_condition_ai(good))
    ambiguous = '```plc\nIF xReady\n y:=TRUE;\n```\n'
    errors = checker.check_condition_ai(ambiguous)
    assert errors and '无法判定' in errors[0], errors
    assert not checker.check_condition_ai('```plc\nLD xReady\nST yStart\n```\n')


def test_condition_marker_variants_are_reported_as_format_errors():
    for variant in ('AI：检查本段入口许可', 'AI:检查本段入口许可', 'ai: 检查本段入口许可'):
        raw = ('```st\nIF x THEN // ' + variant + '\n'
               ' y:=TRUE; // AI: 发布本段请求\nEND_IF;\n```\n')
        errors = checker.check_condition_ai(raw)
        assert errors and '格式' in errors[0], (variant, errors)
    missing = ('```st\nIF x THEN // 作者原有说明\n'
               ' y:=TRUE; // AI: 发布本段请求\nEND_IF;\n```\n')
    errors = checker.check_condition_ai(missing)
    assert errors and '缺少' in errors[0] and '格式' not in errors[0], errors


def test_reference_positive_examples_pass_condition_gate():
    root = Path(__file__).resolve().parents[1]
    for name in ('references/comment-quality.md', 'references/inline-comment-style.md'):
        doc = (root / name).read_text(encoding='utf-8')
        errors = checker.check_condition_ai(doc)
        assert not errors, (name, errors)


def test_condition_lexical_error_is_reported_once():
    import json as jsonlib
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'broken.md'
        path.write_text("```st\nIF x := 'abc THEN // AI: 检查本段入口许可\n```\n", encoding='utf-8')
        command = [sys.executable, '-B', str(Path(__file__).resolve().parents[1] / 'scripts/check_plc_comments.py'),
                   str(path), '--require-condition-ai', '--json']
        result = subprocess.run(command, capture_output=True, text=True)
        assert result.returncode == 1, result.stdout + result.stderr
        errors = jsonlib.loads(result.stdout)[0]['errors']
        lexical = [error for error in errors if '字符串未闭合' in error]
        assert len(lexical) == 1, errors


def test_ai_fragment_spacing_cannot_hide_low_value_note():
    for separator in (' // ', '\t// ', ' //', '//', '  //  '):
        raw = '```st\nIF x THEN y:=TRUE; END_IF; // AI: 未知' + separator + '作者备注\n```\n'
        assert checker.check_condition_ai(raw), repr(separator)
        assert checker.check_text(raw)['errors'], repr(separator)


def test_empty_ai_note_and_duplicate_marker_are_distinguished():
    empty = checker.check_condition_ai('```st\nIF x THEN // AI: \nEND_IF;\n```\n')
    assert any('缺少有效' in error for error in empty), empty
    duplicated = checker.check_condition_ai('```st\nIF x THEN // AI: AI: 检查本段入口许可\nEND_IF;\n```\n')
    assert any('重复 AI' in error for error in duplicated), duplicated


def test_current_handbook_sample_passes_condition_gate():
    root = Path(__file__).resolve().parents[1]
    raw = (root / 'references/example-block-handbook.md').read_text()
    assert not checker.check_condition_ai(raw), checker.check_condition_ai(raw)


if __name__ == '__main__':
    tests = [value for name, value in list(globals().items()) if name.startswith('test_')]
    for test in tests:
        test()
    print(f'concise comment checks passed: {len(tests)} groups')
