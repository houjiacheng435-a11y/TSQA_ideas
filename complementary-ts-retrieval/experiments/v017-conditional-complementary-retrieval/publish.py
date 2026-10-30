"""Publish small audit artifacts, not raw NLQTSBench series or large CPU dumps."""
import gzip
import hashlib
import json
from pathlib import Path
from task import dump

HERE=Path(__file__).parent;ROOT=HERE.parents[1]
OUT=ROOT/'results/v017-conditional-complementary-retrieval'
dest=HERE/'artifacts';dest.mkdir(exist_ok=False)
for name in ['selection.json','cpu-audit.json','cpu-summary.json','boundary.complete.json',
             'fixed-v016-access-audit.json','scores.json','complete.json']:
    with (dest/name).open('xb') as f:f.write((OUT/name).read_bytes())
pilot=json.loads((OUT/'pilot-private.json').read_text())
with gzip.open(dest/'pilot-evaluation-only.json.gz','wt') as f:json.dump(pilot,f)
controls=json.loads((OUT/'controls/records.json').read_text())
full=[]
for r in controls:
    p=OUT/'controls'/r['episode_id']/'llm-calls.jsonl'
    full.append({'record':r,'calls':[json.loads(s) for s in p.read_text().splitlines()]})
with gzip.open(dest/'qwen-control-traces.json.gz','wt') as f:json.dump(full,f)
pre=[]
for d in sorted((OUT/'pilot').iterdir()):
    if not d.is_dir():continue
    rec=json.loads((d/'complete.json').read_text()) if (d/'complete.json').exists() else None
    pre.append({'directory':d.name,'excluded_from_method_ranking':True,'complete':rec,
        'calls':[json.loads(s) for s in (d/'llm-calls.jsonl').read_text().splitlines()] if (d/'llm-calls.jsonl').exists() else [],
        'code':{p.name:p.read_text() for p in d.glob('code-*.py')}})
with gzip.open(dest/'sonar-adapter-precheck-excluded.json.gz','wt') as f:json.dump(pre,f)
dump(dest/'fixed-programs.json',{str(p.parent.name):p.read_text() for p in (OUT/'fixed-v016').glob('*/fixed-program.py')})
environment=ROOT/'experiments/v016-sonarts-qwen-local/artifacts/environment-verified.json'
protocol={'version':'v017','date_beijing':'2026-10-31','gpu':'RTX 4090D 24GB',
    'model':'Qwen/Qwen3-8B','model_revision':'b968826d9c46dd6066d109eabc6255188de91218',
    'official_sonar_commit':'99866c43cd7ceb91a929de745e9f49cea92962e5',
    'environment_reused_from':str(environment),
    'environment_record_sha256':hashlib.sha256(environment.read_bytes()).hexdigest(),
    'server':'vLLM 0.8.5.post1, BF16, max context 16384, max concurrent sequences 1, localhost:8016',
    'decoding':'temperature=0, max_tokens=4096, chat_template_kwargs.enable_thinking=False',
    'cpu_then_gpu_gate':True,'training':False,'paid_api':False,
    'access_contract':'Only initial evidence and numeric context index are visible. Raw trace access is brokered, at most 2 fetches; code retries share the same budget. Evaluation-only files are not passed to child processes or model prompts.',
    'sonar_precheck_outcome':'Stopped and excluded. Adapted runtime/prompt is not equivalent to original Sonar-TS; placeholder outputs and missing builtin occurred. No Sonar performance or complementarity-defect claim.',
    'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(HERE.glob('*')) if p.is_file()}}
dump(dest/'protocol.json',protocol)
manifest=[]
for p in sorted(OUT.rglob('*')):
    if p.is_file():manifest.append({'path':str(p.relative_to(OUT)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
dump(dest/'server-artifact-manifest.json',manifest)
print('Published small v017 audits, complete control traces, excluded adapter traces and reproduction protocol.')
