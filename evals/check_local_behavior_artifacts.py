#!/usr/bin/env python3
"""只读验真冻结批次，再分别汇总原稿、修正稿与外部语义审查记录。

用法：python3 -B evals/check_local_behavior_artifacts.py 批次目录 --candidate 候选技能目录
清单格式见 evals/README.md。支持旧 probe 的 request/content/sha256 JSON 字段；
无冻结清单或无实际请求的旧批拒绝冒认当前候选，不回填历史，不调用模型。
"""
from __future__ import annotations
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import sys

SCORER_FILES = (
    'evals/check_local_behavior_artifacts.py',
    'scripts/check_local_explanation.py',
    'scripts/local_explanation_contract.py',
    'scripts/block_layout.py',
    'scripts/markdown_fences.py',
    'scripts/check_plc_comments.py',
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')


def inside(root: Path, name: str) -> Path:
    if not isinstance(name,str) or not name or Path(name).is_absolute() or '..' in Path(name).parts:
        raise ValueError('清单路径必须是根目录内的相对路径')
    result=(root/name).resolve()
    if not result.is_relative_to(root.resolve()): raise ValueError('清单路径越界')
    return result


def verified(root: Path, name: str, expected: str, label: str) -> bytes:
    data=inside(root,name).read_bytes()
    if not isinstance(expected,str) or sha(data)!=expected:
        raise ValueError(label+'哈希不一致：'+name)
    return data


def json_object(data: bytes, label: str) -> dict:
    value=json.loads(data)
    if not isinstance(value,dict): raise ValueError(label+'须为 JSON 对象')
    return value


def candidate_checker(candidate: Path):
    scripts=str((candidate/'scripts').resolve())
    if scripts in sys.path:
        sys.path.remove(scripts)
    sys.path.insert(0,scripts)
    module_names=[Path(name).stem for name in SCORER_FILES if name.startswith('scripts/')]
    for name in module_names:
        sys.modules.pop(name,None)
    checker=importlib.import_module('check_local_explanation')
    for name in module_names:
        module=sys.modules.get(name)
        if module is None or Path(module.__file__).resolve()!=inside(candidate,'scripts/'+name+'.py'):
            raise ValueError('评分器依赖未从候选加载：'+name)
    return checker.check_text


def check_batch(batch: Path, candidate: Path, manifest_name: str='frozen-manifest.json') -> dict:
    """先对全部证据闭链，任一不一致即抛错，评分不先于验真。"""
    manifest=json_object(inside(batch,manifest_name).read_bytes(),'冻结清单')
    frozen=inside(batch,manifest['frozen_dir'])
    files=manifest['files'];guidance=manifest['guidance_files']
    if not isinstance(files,dict) or not files or not isinstance(guidance,list) or not guidance or len(set(guidance))!=len(guidance):
        raise ValueError('冻结文件/指导清单为空或重复')
    for name in guidance:
        inside(frozen,name)
        if name not in files: raise ValueError('冻结指导未登记：'+name)
    for name,digest in files.items():
        verified(frozen,name,digest,'冻结文件')
        verified(candidate,name,digest,'候选文件')
    scorer_files=manifest.get('scorer_files')
    if not isinstance(scorer_files,dict) or set(scorer_files)!=set(SCORER_FILES):
        raise ValueError('评分器冻结清单缺失或依赖集合不完整')
    for name in SCORER_FILES:
        verified(frozen,name,scorer_files[name],'冻结评分器')
        verified(candidate,name,scorer_files[name],'候选评分器')
    running_name='evals/check_local_behavior_artifacts.py'
    if sha(Path(__file__).read_bytes())!=scorer_files[running_name]:
        raise ValueError('实际运行的评分器不属于冻结候选')
    check_text=candidate_checker(candidate)
    system='\n\n'.join('=== '+name+' ===\n'+inside(frozen,name).read_bytes().decode('utf-8') for name in guidance)
    system_sha=sha(system.encode('utf-8'))
    if system_sha!=manifest['system_sha256']: raise ValueError('冻结合成指导哈希不一致')
    meta=json_object(verified(batch,'meta.json',manifest['meta_sha256'],'批次元信息'),'元信息')
    if meta.get('system_sha256')!=system_sha: raise ValueError('批次指导不是此冻结快照')
    expected=manifest['expected_samples']; samples=manifest['samples']
    if type(expected) is not int or expected<1 or not isinstance(samples,list) or len(samples)!=expected:
        raise ValueError('样本数缺失或与完整批期望不一致')
    if meta.get('reps',expected)!=expected: raise ValueError('样本数与原始批次元信息不一致')
    source=meta.get('source');prompt=meta.get('prompt')
    if not isinstance(source,str) or not source or not isinstance(prompt,str) or not prompt:
        raise ValueError('样本源/提示词为空，不能验收完整批')
    if (not isinstance(meta.get('model'),str) or not meta['model'].strip()
            or type(meta.get('max_tokens')) is not int or meta['max_tokens']<1
            or ('provider' in meta and (not isinstance(meta['provider'],str) or not meta['provider'].strip()))):
        raise ValueError('批次元信息 model/max_tokens 缺失或类型无效；provider 若提供须为非空字符串')
    ids=set(); paths=set(); validated=[]; common_request=None
    for sample in samples:
        identifier=sample['id']
        if type(identifier) is not int or identifier<1 or identifier in ids:
            raise ValueError('样本 ID 缺失或重复')
        ids.add(identifier)
        artifact=sample['artifact']
        if artifact in paths: raise ValueError('样本产物重复登记')
        paths.add(artifact)
        record=json_object(verified(batch,artifact,sample['sha256'],'样本 JSON'),'样本')
        if record.get('sample')!=identifier: raise ValueError('样本 ID 与原 JSON 不一致')
        content=record.get('content');request=record.get('request')
        if (record.get('error') or not isinstance(content,str) or not content.strip()
                or record.get('finish_reason')!='stop' or not isinstance(request,dict)):
            raise ValueError(f'样本 {identifier} 请求缺失、报错、空输出或截断，不是完整批')
        if (request.get('model')!=meta['model'] or request.get('max_tokens')!=meta['max_tokens']
                or not isinstance(request.get('model'),str) or type(request.get('max_tokens')) is not int):
            raise ValueError(f'样本 {identifier} 实际请求 model/max_tokens 与批次元信息不符')
        if sha(content.encode('utf-8'))!=record.get('sha256'):
            raise ValueError(f'样本 {identifier} 原回答内容哈希不一致')
        answer=verified(batch,sample['answer'],sample['answer_sha256'],'原回答')
        if answer.decode('utf-8')!=content: raise ValueError('样本 JSON 与保存原稿不一致')
        request_sha=sha(canonical(request))
        messages=request.get('messages')
        if (request_sha!=sample['request_sha256'] or not isinstance(messages,list)
                or messages!=[{'role':'system','content':system},{'role':'user','content':prompt}]):
            raise ValueError(f'样本 {identifier} 实际请求与冻结指导/提示词不一致')
        if common_request is not None and canonical(request)!=common_request:
            raise ValueError('每个实际请求的指导、提示词或采样配置不一致')
        common_request=canonical(request)
        corrected=None;review=None
        if sample.get('corrected') is not None:
            entry=sample['corrected']
            corrected=verified(batch,entry['path'],entry['sha256'],'修正稿').decode('utf-8')
            if not corrected.strip(): raise ValueError('修正稿为空')
        if sample.get('semantic_review') is not None:
            entry=sample['semantic_review']
            review=json_object(verified(batch,entry['path'],entry['sha256'],'语义审查记录'),'审查记录')
            target=entry['target']
            if target not in ('original','corrected') or (target=='corrected' and corrected is None):
                raise ValueError('语义审查绑定目标不存在')
            document=corrected if target=='corrected' else content
            if (review.get('document_sha256')!=sha(document.encode('utf-8'))
                    or type(review.get('reviewed')) is not bool or type(review.get('accepted')) is not bool
                    or not isinstance(review.get('issues'),list) or not isinstance(review.get('basis'),str)
                    or not review['basis'].strip() or (review['accepted'] and (not review['reviewed'] or review['issues']))):
                raise ValueError('语义审查绑定/结论/具体依据无效；不采信生成方自报')
        returned=record.get('model_returned')
        validated.append((identifier,content,corrected,review,returned,request.get('model')))
    # 所有候选、请求、原稿和审查哈希均验证后，才开始格式评分。
    original_passed=0;corrected_passed=0;corrected_executed=0;reviewed=0;accepted=0;results=[]
    for identifier,content,corrected,review,returned,requested in validated:
        original_result=check_text(content,source)
        original_passed+=int(not original_result['errors'])
        corrected_result=None
        if corrected is not None:
            corrected_executed+=1;corrected_result=check_text(corrected,source)
            corrected_passed+=int(not corrected_result['errors'])
        if review is not None:
            reviewed+=int(review['reviewed']);accepted+=int(review['reviewed'] and review['accepted'])
        results.append({'sample':identifier,'original':original_result,
                        'corrected':corrected_result if corrected_result is not None else '未执行',
                        'semantic_review':review if review is not None else '未审',
                        'model_requested':requested,
                        'model_returned':returned,
                        'model_alias_warning':bool(returned and returned!=requested)})
    return {'status':'scored','expected_samples':expected,'requests_complete':len(validated),
            'original_format_passed':original_passed,
            'corrected_executed':corrected_executed,
            'corrected_format_passed':corrected_passed if corrected_executed else '未执行',
            'semantics_reviewed':reviewed,'semantics_passed':accepted,
            'semantic_scope':'仅汇总已绑定外部审查记录，不由本工具判断自然语言或 PLC 语义',
            'provider':meta.get('provider'),'provider_scope':'仅为可选批次调用来源记录，未验证服务器身份',
            'system_sha256':system_sha,'samples':results}


def main(argv: list[str] | None = None) -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('batch',type=Path);ap.add_argument('--candidate',required=True,type=Path)
    ap.add_argument('--manifest',default='frozen-manifest.json')
    args=ap.parse_args(argv)
    try:
        result=check_batch(args.batch,args.candidate,args.manifest)
    except (OSError,UnicodeError,ValueError,KeyError,TypeError) as exc:
        print('ERROR 冻结批次拒绝评分：'+str(exc));return 1
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0


if __name__=='__main__': raise SystemExit(main())
