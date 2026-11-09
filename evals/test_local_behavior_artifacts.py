#!/usr/bin/env python3
"""冻结链先验真，再评分；全用临时受控产物，不联网或修改旧批。"""
from pathlib import Path
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from test_local_explanation_contract import ROOT, VALID, SOURCE

CLI=ROOT/'evals/check_local_behavior_artifacts.py'


def sha(data):
    return hashlib.sha256(data if isinstance(data,bytes) else data.encode()).hexdigest()


def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    return sha(path.read_bytes())


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.batch=self.root/'batch';self.batch.mkdir()
        self.candidate=self.root/'candidate';self.candidate.mkdir()
        self.freeze=self.batch/'frozen';self.freeze.mkdir()
        files={}
        for name,content in (('SKILL.md','已冻结的局部指导\n'),('references/local-code-explanation.md','五部分原码契约\n')):
            for base in (self.freeze,self.candidate):
                p=base/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
            files[name]=sha(content)
        self.scorer_names=('evals/check_local_behavior_artifacts.py','scripts/check_local_explanation.py',
                           'scripts/local_explanation_contract.py','scripts/block_layout.py',
                           'scripts/markdown_fences.py','scripts/check_plc_comments.py')
        self.scorer_files={}
        for name in self.scorer_names:
            content=(ROOT/name).read_bytes()
            self.scorer_files[name]=sha(content)
            for base in (self.freeze,self.candidate):
                target=base/name
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
        self.guidance=list(files)
        self.system='\n\n'.join('=== '+name+' ===\n'+(self.freeze/name).read_text() for name in self.guidance)
        self.prompt='给初学者讲解这个片段，原码如下：\n'+SOURCE
        self.request={'model':'controlled-local-fixture','messages':[{'role':'system','content':self.system},{'role':'user','content':self.prompt}],'max_tokens':8000}
        self.meta={'source':SOURCE,'prompt':self.prompt,'system_sha256':sha(self.system),'reps':2,
                   'model':'controlled-local-fixture','max_tokens':8000,'provider':'controlled-test-provider'}
        save(self.batch/'meta.json',self.meta)
        self.manifest={'expected_samples':2,'frozen_dir':'frozen','files':files,'scorer_files':self.scorer_files,'guidance_files':self.guidance,
                       'system_sha256':sha(self.system),'meta_sha256':sha((self.batch/'meta.json').read_bytes()),'samples':[]}
        for i in (1,2):
            record={'sample':i,'arm':'after','request':copy.deepcopy(self.request),'model_returned':'controlled-local-fixture',
                    'finish_reason':'stop','content':VALID,'sha256':sha(VALID)}
            path=self.batch/f'{i}.json';digest=save(path,record)
            (self.batch/f'{i}.md').write_text(VALID)
            self.manifest['samples'].append({'id':i,'artifact':f'{i}.json','sha256':digest,
                                            'answer':f'{i}.md','answer_sha256':sha(VALID),'request_sha256':sha(canonical(self.request))})
        self.persist()

    def persist(self):save(self.batch/'frozen-manifest.json',self.manifest)

    def persist_meta(self):
        self.manifest['meta_sha256']=save(self.batch/'meta.json',self.meta)
        self.persist()

    def mutate_record(self,i,change):
        sample=self.manifest['samples'][i-1];path=self.batch/sample['artifact'];record=json.loads(path.read_text());change(record)
        sample['sha256']=save(path,record)
        sample['request_sha256']=sha(canonical(record.get('request')))
        self.persist()

    def invoke(self,cli=CLI,preload=None):
        command=[sys.executable,'-B',str(cli),str(self.batch),'--candidate',str(self.candidate)]
        if preload is not None:
            command=[sys.executable,'-B','-c',preload,str(self.batch),'--candidate',str(self.candidate)]
        return subprocess.run(command,
                              capture_output=True,text=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})

    def reject(self,reason):
        result=self.invoke()
        self.assertEqual(result.returncode,1,result.stdout+result.stderr)
        self.assertIn('ERROR',result.stdout)
        self.assertIn(reason,result.stdout)
        self.assertNotIn('original_format_passed',result.stdout, '证据拒绝前不得输出评分汇总')

    def test_matching_frozen_snapshot_and_old_probe_json_shape_are_scored(self):
        self.assertTrue(CLI.is_file(),'缺少冻结批次验真/评分入口')
        result=self.invoke();self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        data=json.loads(result.stdout)
        self.assertEqual(data['requests_complete'],2)
        self.assertEqual(data['original_format_passed'],2)
        self.assertEqual(data['corrected_format_passed'],'未执行')
        self.assertEqual(data['semantics_reviewed'],0)
        self.assertEqual(data['semantics_passed'],0)

    def test_old_guidance_cannot_claim_current_candidate(self):
        (self.candidate/'references/local-code-explanation.md').write_text('当前已修改指导\n')
        self.reject('候选')

    def test_actual_request_mismatch_refuses_entire_batch_before_scoring(self):
        self.mutate_record(2,lambda r:r['request']['messages'][0].update(content='旧指导'))
        self.reject('实际请求')

    def test_actual_request_prompt_or_settings_must_match_every_sample(self):
        self.mutate_record(2,lambda r:r['request'].update(max_tokens=1))
        self.reject('实际请求')

    def test_declared_model_and_token_limit_bind_every_request(self):
        self.mutate_record(1,lambda r:r['request'].update(model='gateway-model-alias',max_tokens=2000))
        self.mutate_record(2,lambda r:r['request'].update(model='gateway-model-alias',max_tokens=2000))
        self.reject('元信息')

    def test_missing_or_mistyped_sampling_metadata_is_rejected(self):
        for key,value in (('model',None),('model',123),('max_tokens',None),('max_tokens','8000'),
                          ('max_tokens',True),('provider',123),('provider','  ')):
            with self.subTest(key=key):
                self.meta[key]=value
                if value is None:self.meta.pop(key)
                self.persist_meta()
                self.reject('元信息')
                self.meta={'source':SOURCE,'prompt':self.prompt,'system_sha256':sha(self.system),'reps':2,
                           'model':'controlled-local-fixture','max_tokens':8000,'provider':'controlled-test-provider'}
                self.persist_meta()

    def test_model_returned_alias_is_recorded_without_rejecting(self):
        self.mutate_record(1,lambda r:r.update(model_returned='gateway-alias-v2'))
        result=self.invoke();self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        data=json.loads(result.stdout)
        self.assertEqual(data['samples'][0]['model_returned'],'gateway-alias-v2')
        self.assertTrue(data['samples'][0]['model_alias_warning'])
        self.assertEqual(data['samples'][0]['model_requested'],self.meta['model'])
        self.assertEqual(data['provider'],self.meta['provider'])
        self.assertIn('未验证服务器身份',data['provider_scope'])
        self.assertNotIn('provider',self.request)

    def test_provider_is_optional_provenance_and_is_never_required_in_request(self):
        self.meta.pop('provider');self.persist_meta()
        result=self.invoke();self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        data=json.loads(result.stdout)
        self.assertIsNone(data['provider'])
        self.assertIn('未验证服务器身份',data['provider_scope'])

    def test_request_model_and_token_types_are_checked(self):
        for key,value in (('model',None),('model',123),('max_tokens',None),('max_tokens','8000'),('max_tokens',True)):
            original=(self.batch/'1.json').read_bytes();manifest=copy.deepcopy(self.manifest)
            self.mutate_record(1,lambda r:r['request'].update({key:value}))
            with self.subTest(key=key,value=value):self.reject('元信息')
            (self.batch/'1.json').write_bytes(original);self.manifest=manifest;self.persist()

    def test_scorer_dependencies_are_frozen_and_loaded_from_candidate(self):
        old=self.manifest.pop('scorer_files');self.persist();self.reject('评分器')
        self.manifest['scorer_files']=old;self.persist()
        for name in self.scorer_names:
            original=(self.candidate/name).read_bytes()
            (self.candidate/name).write_bytes(original+b'\n# dependency changed\n')
            with self.subTest(name=name):self.reject('评分器')
            (self.candidate/name).write_bytes(original)

    def test_candidate_checker_cannot_reuse_foreign_imported_dependencies(self):
        preload=('import sys,runpy; sys.path.insert(0,'+repr(str(ROOT/'scripts'))+'); '
                 'import local_explanation_contract as foreign; foreign.BLOCK_PARTS=("FOREIGN",)*5; '
                 'sys.argv[0]='+repr(str(CLI))+'; runpy.run_path('+repr(str(CLI))+',run_name="__main__")')
        result=self.invoke(preload=preload)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(json.loads(result.stdout)['original_format_passed'],2)

    def test_running_scorer_with_different_bytes_is_rejected(self):
        other=self.root/'foreign-scorer.py';other.write_bytes(CLI.read_bytes()+b'\n# foreign copy\n')
        result=self.invoke(cli=other)
        self.assertEqual(result.returncode,1,result.stdout+result.stderr)
        self.assertIn('实际运行的评分器',result.stdout)

    def test_missing_empty_truncated_samples_cannot_be_called_complete(self):
        for change in (lambda r:r.update(content='',sha256=sha('')),
                       lambda r:r.update(finish_reason='length'),lambda r:r.pop('request')):
            original=(self.batch/'2.json').read_bytes();manifest=copy.deepcopy(self.manifest)
            self.mutate_record(2,change)
            with self.subTest(change=change):self.reject('样本')
            (self.batch/'2.json').write_bytes(original);self.manifest=manifest;self.persist()
        self.manifest['samples'].pop();self.persist();self.reject('样本数')

    def test_hashes_frozen_files_answers_and_requests_are_checked(self):
        (self.batch/'1.md').write_text('被改原回答')
        self.reject('哈希')
        (self.batch/'1.md').write_text(VALID)
        (self.freeze/'SKILL.md').write_text('被改冻结指导')
        self.reject('冻结')

    def test_original_format_failures_and_corrected_artifacts_are_separate(self):
        bad=VALID.replace('**代码职责**','**缺失**')
        self.mutate_record(1,lambda r:r.update(content=bad,sha256=sha(bad)))
        (self.batch/'1.md').write_text(bad)
        sample=self.manifest['samples'][0];sample['answer_sha256']=sha(bad)
        (self.batch/'1-corrected.md').write_text(VALID)
        sample['corrected']={'path':'1-corrected.md','sha256':sha(VALID)}
        self.persist();result=self.invoke()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr);data=json.loads(result.stdout)
        self.assertEqual(data['original_format_passed'],1)
        self.assertEqual(data['corrected_format_passed'],1)
        self.assertEqual(data['corrected_executed'],1)
        self.assertEqual(data['requests_complete'],2)

    def test_semantic_record_is_bound_to_document_not_self_report(self):
        review={'document_sha256':sha(VALID),'reviewed':True,'accepted':False,'issues':['具体推演需复核'],
                'basis':'外部独立人工审查记录；未把映射存在当作语义证明'}
        digest=save(self.batch/'review.json',review)
        self.manifest['samples'][0]['semantic_review']={'path':'review.json','sha256':digest,'target':'original'}
        self.persist();result=self.invoke()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr);data=json.loads(result.stdout)
        self.assertEqual(data['semantics_reviewed'],1);self.assertEqual(data['semantics_passed'],0)
        review['document_sha256']=sha('另一份稿')
        self.manifest['samples'][0]['semantic_review']['sha256']=save(self.batch/'review.json',review)
        self.persist();self.reject('语义审查绑定')

    def test_path_traversal_and_duplicate_sample_ids_are_rejected(self):
        self.manifest['samples'][1]['id']=1;self.persist();self.reject('样本')
        self.manifest['samples'][1]['id']=2
        self.manifest['guidance_files']=['../other.md'];self.persist();self.reject('路径')


if __name__=='__main__': unittest.main(verbosity=2)
