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


if __name__ == '__main__':
    tests = [value for name, value in list(globals().items()) if name.startswith('test_')]
    for test in tests:
        test()
    print(f'concise comment checks passed: {len(tests)} groups')
