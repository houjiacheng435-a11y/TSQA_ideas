"""Run unmodified official TT-SAX encoder + regex search on a native NLQTSBench file.
An execution smoke test only: no claim to reproduce the paper's LLM-to-regex scores.
"""
import os
import pathlib,sys,json,time,hashlib
import pandas as pd,numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[2];OUT=pathlib.Path(os.environ.get('V020_OUT',str(ROOT/'results/v020-evidence-fidelity')));VENDOR=pathlib.Path('/root/autodl-tmp/cf-run/vendor/v020/tt-sax');sys.path.insert(0,str(VENDOR))
from ttsax import ttsax,encoding_card
from symq.search import search
ids=json.load(open(ROOT/'experiments/v019-cpu-failure-atlas/protocol.json'))['ids'];tid=sorted(ids)[0];p=next((ROOT/'data').glob('**/'+tid+'.csv'));df=pd.read_csv(p);native=json.load(open('/root/autodl-tmp/cf-run/vendor/Sonar-TS-v016-direct/nlqtsbench/tasks.json'));task=next(t for t in native if t['id']==tid);ch=str(task['channel']);df.timestamp=pd.to_datetime(df.timestamp);start=time.perf_counter();words={str(d.date()):ttsax(g[ch].to_numpy(),w=24) for d,g in df.groupby(df.timestamp.dt.floor('D'))};secs=time.perf_counter()-start
rows=[]
for question,pattern in [('At least three consecutive rising inter-segment trend letters','[rR]{3,}'),('At least three consecutive falling inter-segment trend letters','[fF]{3,}')]:
 t=time.perf_counter();candidates,timeout=search(words,pattern);rows.append({'query':question,'pattern':pattern,'candidate_dates':candidates,'timeout':timeout,'seconds':time.perf_counter()-t})
result={'official_commit':'95fe2c1d50561538a6fe822ec6a97e0f0829ff80','native_source_id':tid,'channel':ch,'days':len(words),'encoding_seconds':secs,'bytes_symbol_strings':sum(len(v.encode()) for v in words.values()),'input_csv_bytes':p.stat().st_size,'input_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'words':words,'encoding_card':encoding_card(),'searches':rows,'interpretation':'Reference encoder and official regex search executed on real native data. Handwritten literal symbolic queries; no benchmark answer labels used, no paper-level NLQ evaluation or new SOTA score.'}
(OUT/'ttsax-native-smoke.json').write_text(json.dumps(result,indent=2)+'\n');print('TT-SAX native smoke',len(words),'days',secs,'seconds')
