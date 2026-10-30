"""CPU diagnostic: instantiate upstream numerical recipes with correct parameters.

These are correct program/parameter instantiations, not a guarantee that the
upstream heuristics equal the benchmark's hidden generative label rule.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from task import dump

ap=argparse.ArgumentParser();ap.add_argument('--official',type=Path,required=True)
a=ap.parse_args()
ROOT=Path(__file__).resolve().parents[2];OLD=ROOT/'results/v016-sonarts-qwen-local'
OUT=ROOT/'results/v017-conditional-complementary-retrieval/fixed-v016'
OUT.mkdir(parents=True,exist_ok=False)
sys.path.insert(0,str(a.official))
from sonar_ts import evaluator
from sonar_ts.postprocess import format_prediction
tasks={t['id']:t for t in json.loads((OLD/'tasks-selected.json').read_text())}
old={r['task_id']:r for r in json.loads((OLD/'pilot10/records.json').read_text())}
rows=[]
for tid in ['L3_T3_Causal_Anomaly_00386','L3_T1_Composite_Trend_00014','L3_T1_Composite_Trend_00025','L3_T1_Composite_Trend_00034']:
    t=tasks[tid];d=OUT/tid;d.mkdir()
    if 'Causal' in tid:
        source=a.official/'sonar_ts/skills/library/causal-anomaly-correlation.md'
        code=re.findall(r'```python\n(.*?)```',source.read_text(),re.S)[0]
        code=code.replace('YEAR = <year>','YEAR = 2022').replace('<X>','67').replace('<year>','2022')
        code='question = '+repr(t['question'])+'\n'+code
    else:
        source=a.official/'sonar_ts/skills/library/composite-trend-topk.md'
        code=re.findall(r'```python\n(.*?)```',source.read_text(),re.S)[0]
        m=re.search(r'channel (\d+) during (\d+)',t['question']);ch,year=m.groups()
        pattern=re.search(r"pattern '([^']+)'",t['question']).group(1)
        kinds=[part.strip().split()[-1] for part in pattern.split(', then ')]
        target=re.search(r'where the (.+?) segment is the (\w+)',t['question'])
        adj,kind=target[1].split();sup=target[2]
        code=code.replace('<channel id>',ch).replace('<year int>',year)
        code=code.replace('<ordered kind list from the pattern, e.g. ["stable","fall","fall"]>',repr(kinds))
        code=code.replace('<the kind the question ranks on: rise|fall|stable>',kind)
        code=code.replace('<the adjective on that segment, e.g. slow>',adj).replace('<the superlative word, e.g. slowest>',sup)
    code+='\nimport json\nprint(json.dumps({"_result":_result}))\n'
    (d/'fixed-program.py').write_text(code)
    env=dict(os.environ,V016_SQL_TRACE=str(d/'sql.jsonl.gz'),V016_OFFICIAL_RUNNER=str(a.official/'sonar_ts/_runner.py'),OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
    runner=ROOT/'experiments/v016-sonarts-qwen-local/traced_runner.py'
    proc=subprocess.run([sys.executable,str(runner),str(OLD/'databases'/f'{tid}.sqlite'),str(d/'fixed-program.py')],env=env,capture_output=True,text=True,timeout=60)
    assert proc.returncode==0,proc.stderr
    value=json.loads(proc.stdout.splitlines()[-1])['_result']
    pred=format_prediction(t,value)
    score,detail=evaluator.score_one(t['eval_metric'],pred,t.get('ground_truth',t.get('answer')))
    rec={'id':tid,'old_status':old[tid]['final_status'],'old_score':old[tid]['score'],
         'fixed_score':score,'prediction':pred,'breakdown':detail,'stdout':proc.stdout,'stderr':proc.stderr,
         'source_skill':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
         'note':'No LLM. Correct substitution into existing upstream numerical recipe; low scores remain possible if its heuristic differs from reference labels.'}
    dump(d/'result.json',rec);rows.append(rec)
dump(OUT/'summary.json',rows)
print(json.dumps(rows,ensure_ascii=False,indent=2))
