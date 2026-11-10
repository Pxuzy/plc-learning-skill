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
        good = '```st\nIF x THEN // AI: 检查本段入口许可\n y:=TRUE; // AI: 发布本段请求\nEND_IF;\n```\n'
        command = [sys.executable, '-B', str(Path(__file__).resolve().parents[1] / 'scripts/check_plc_comments.py'), str(path), '--require-condition-ai', '--json']
        path.write_text(good, encoding='utf-8')
        result = subprocess.run(command, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        path.write_text(good.replace(' // AI: 检查本段入口许可', ''), encoding='utf-8')
        result = subprocess.run(command, capture_output=True, text=True)
        assert result.returncode == 1 and '条件判断行' in result.stdout, result.stdout


if __name__ == '__main__':
    tests = [value for name, value in list(globals().items()) if name.startswith('test_')]
    for test in tests:
        test()
    print(f'concise comment checks passed: {len(tests)} groups')
