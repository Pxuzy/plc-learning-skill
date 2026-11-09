#!/usr/bin/env python3
"""限定教学夹具的独立纸面重算；不为任意中文正文打语义分。"""
from pathlib import Path
import re
import unittest
from test_local_explanation_contract import ROOT, VALID
from local_explanation_contract import tables
from test_entry_routing import read_heading

# 独立给定输入。两条轨迹分别清零；首次 IN 真建立 t0，非保持 TON 假设。
TRACES = {
    'A': [(0,True,True,False),(250,True,True,False),(260,False,True,True),
          (270,True,True,False),(370,True,True,False)],
    'B': [(0,True,True,True),(250,True,True,True),(260,True,True,False)],
}


def expected_trace(events):
    start=None; run=False; et=0; q=False; ready=False; result=[]
    for time,request,permit,fault in events:
        before=(et,q,run,ready)
        if not (request and permit): start=None; et=0; q=False
        else:
            if start is None: start=time
            et=min(time-start,200); q=et>=200
        if fault: run=False
        elif q and permit: run=True
        ready=permit and not fault
        result.append((time,(request,permit,fault),before,(et,q,run,ready)))
    return result


def states(cell):
    values={}
    for match in re.finditer(r'(ET|Q|Run|Ready)=(\d+)(?:ms)?|(Q|Run|Ready)=(TRUE|FALSE)',cell):
        if match[1]: values[match[1]]=int(match[2])
        else: values[match[3]]=match[4]=='TRUE'
    return tuple(values.get(key) for key in ('ET','Q','Run','Ready'))


def review_fixed_ledger(doc):
    rows=next(rows for header,rows in tables(doc) if header[0]=='阶段/执行')
    for name,events in TRACES.items():
        actual=[row for row in rows if row[0].startswith(name+' 第')]
        assert len(actual)==len(events), '固定轨迹执行数漂移'
        for row, (time,inputs,before,after) in zip(actual,expected_trace(events)):
            assert f't={time}ms' in row[0], row[0]
            assert states(row[1])==before, (row[0],'前值',states(row[1]),before)
            assert states(row[3])==after, (row[0],'结果',states(row[3]),after)
    return True


class LocalTeachingReview(unittest.TestCase):
    def test_reader_trigger_and_cli_loop_are_actionable_sections(self):
        route=read_heading('references/local-code-explanation.md','## 出稿与局部修正闭环 🛠️')
        self.assertIn('references/workflow.md',route)
        self.assertIn('局部产物校验',route)
        self.assertIn('未执行',route)
        self.assertRegex(route,r'仅.*有工具.*实际.*产物校验')
        self.assertNotIn('scripts/check_local_explanation.py',route)
        loop=read_heading('references/workflow.md','### 局部产物校验')
        for term in ('scripts/check_local_explanation.py','最多 3 轮','未执行',
                     'explanation: L1-L1','unreviewed:','source-eof: none'):
            self.assertIn(term,loop)
        # 执行方法下沉后仍拒绝缺命令或缺轮数边界的变异，不能只检查路由存在。
        for term in ('scripts/check_local_explanation.py','最多 3 轮'):
            self.assertEqual(loop.count(term),1)
            bad=loop.replace(term,'',1)
            self.assertNotEqual(bad,loop)
            with self.assertRaises(AssertionError):
                self.assertIn(term,bad)
        beginner=read_heading('references/local-code-explanation.md','## 零基础正文覆盖（仅按读者需求启用） 🎓')
        self.assertIn('第三部分',beginner)
        self.assertIn('explanation: L1-L1',beginner)
        self.assertIn('unreviewed:',beginner)

    def test_first_summary_and_function_placeholders_require_local_assumptions(self):
        for name in ('local-code-explanation.md','one-page-prompt.md'):
            text=(ROOT/'references'/name).read_text(encoding='utf-8')
            for label in ('一句话说清','功能定位'):
                placeholder=re.search(r'\*\*'+label+r'\*\*：<([^>]+)>',text)
                self.assertIsNotNone(placeholder)
                self.assertIn('假设',placeholder[1],name+' / '+label+' 缺首处假设提示')

    def test_fixed_ledger_matches_independent_timing_and_storage_oracle(self):
        self.assertTrue(review_fixed_ledger(VALID))
        self.assertEqual(expected_trace(TRACES['A'])[-1][-1],(100,False,False,True))
        self.assertEqual(expected_trace(TRACES['B'])[-1][-1],(200,True,True,True))

    def test_reset_under_200ms_wrong_q_and_copied_run_are_rejected(self):
        row=next(line for line in VALID.splitlines() if line.startswith('| A 第5次'))
        for original,changed in (('ET=100ms,Q=FALSE,Run=FALSE','ET=200ms,Q=TRUE,Run=FALSE'),
                                 ('ET=100ms,Q=FALSE,Run=FALSE','ET=100ms,Q=FALSE,Run=TRUE')):
            bad=VALID.replace(row,row.replace(original,changed))
            self.assertNotEqual(bad,VALID)
            with self.subTest(changed=changed), self.assertRaises(AssertionError):review_fixed_ledger(bad)

    def test_fault_already_timed_release_must_not_restart_timer(self):
        row=next(line for line in VALID.splitlines() if line.startswith('| B 第3次'))
        bad=VALID.replace(row,row.replace('ET=200ms,Q=TRUE,Run=TRUE','ET=0,Q=FALSE,Run=FALSE'))
        self.assertNotEqual(bad,VALID)
        with self.assertRaises(AssertionError):review_fixed_ledger(bad)

    def test_teaching_cases_name_concrete_coverage_and_late_assumption_counterexamples(self):
        cases=(ROOT/'evals/cases.md').read_text(encoding='utf-8')
        review=read_heading('evals/cases.md','### Case 30 独立反例审查表')
        # 登记的是待执行的人工成品审查；不是关键词打语义分。
        rows=next(rows for header,rows in tables(review) if header[0]=='反例')
        self.assertEqual(len(rows),6)
        self.assertIn('新手复述',cases)


if __name__=='__main__': unittest.main(verbosity=2)
