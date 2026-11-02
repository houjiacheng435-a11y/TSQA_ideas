"""Official Sonar-TS end-to-end pipeline + existing local Qwen3 (adapted baseline).
New directories only. DB adapter preserves ECG subsecond timestamps.
"""
import dataclasses,gzip,importlib.util,json,os,pathlib,sys,time,sqlite3,hashlib
import numpy as np,pandas as pd,yaml
ROOT=pathlib.Path(__file__).resolve().parents[2];OUT=pathlib.Path(os.environ.get('V020_OUT',str(ROOT/'results/v020-evidence-fidelity')))/'sonar';DATA=ROOT/'data/v020-evidence-fidelity';OFFICIAL=pathlib.Path('/root/autodl-tmp/cf-run/vendor/Sonar-TS-v016-direct')
sys.path.insert(0,str(OFFICIAL))
from sonar_ts import _paths
_paths.DATABASES_DIR=pathlib.Path(os.environ.get('V020_DB_DIR',str(DATA/'sonar-databases')))
from sonar_ts import storage,offline,pipeline,executor,evaluator
spec=importlib.util.spec_from_file_location('v016client',ROOT/'experiments/v016-sonarts-qwen-local/run.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)

def dump(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,default=str)+'\n')
def make_db(t,df):
 p=_paths.db_path_for(t['id']);p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():return
 db=storage.TaskDatabase(t['id']);db.init_feature_schema();df.to_sql('raw_data',db.connect(),index=False);db.connect().execute('CREATE INDEX idx_raw_ts ON raw_data(timestamp)');db.connect().commit()
 long=df.assign(timestamp=pd.to_datetime(df.timestamp)).melt('timestamp',var_name='channel_id',value_name='value')
 cfg=yaml.safe_load((OFFICIAL/'configs/offline.yaml').read_text());features=offline.compute_all_features(long,cfg['views'],cfg['sax']['alphabet'])
 for k,v in features.items():
  if not v.empty:db.write_feature_table(k,v)
 db.close()

def prepare():
 OUT.mkdir(parents=True,exist_ok=True);tasks=json.load(open(OFFICIAL/'nlqtsbench/tasks.json'));native=[]
 for t in sorted([t for t in tasks if t['subtask']=='Global Aggregation'],key=lambda x:x['id']):
  found=list((ROOT/'data').glob('**/'+t['id']+'.csv'))
  if not found:
   from acquire import fetch
   rel=t['ts_data_path']; dest=DATA/'native'/pathlib.Path(rel).name
   row=fetch('mrtan/NLQTSBench','81571171c5c614d01698497626bff8eb6ad8dcf4',rel,dest)
   catalog=json.load(open(ROOT/'data/pilot30-v004/dataset-file-catalog.json'))
   upstream=next(z for z in catalog if z['path']==rel); blob=dest.read_bytes()
   assert len(blob)==upstream['size'] and hashlib.sha1(b'blob '+str(len(blob)).encode()+b'\0'+blob).hexdigest()==upstream['oid']
   dump(OUT/(t['id']+'-source.json'),dict(row,upstream=upstream));found=[dest]
  if found:
   native.append(t);df=pd.read_csv(found[0]);make_db(t,df)
  if len(native)==2:break
 assert len(native)==2
 x=np.array(np.load(DATA/'raw/100/100.npy',mmap_mode='r')[16384:16384+131072]);sys.path.insert(0,str(pathlib.Path(__file__).parent));from core import answer
 public={
 'exists05':"Return 1 if at least one ECG1 sample is >= 0.5, otherwise 0.",
 'count':"Count maximal contiguous runs of ECG1 samples >= 0.5. A new run begins at the first sample if it qualifies, or whenever a below-threshold sample is followed by a qualifying sample. Return the integer run count; do not count individual samples.",
 'duration':"Count the number of ECG1 samples with value >= 1.0. Return the integer number of samples, not seconds.",
 'maximum':"Return the maximum value of ECG1 rounded to three decimals.",
 'trend':"Return 1 if the mean ECG1 value in the second half of the chronologically ordered samples is strictly larger than in the first half, otherwise 0.",
 'cooccur':"Return 1 if there is at least one timestamp when both ECG1 and ECG2 are >= 0.5 simultaneously; otherwise return 0."}
 unified=[]
 # Freeze complete task IDs and conditions before calling any model.
 for view in ['full','paa64']:
  vals=x if view=='full' else x.reshape(-1,64,2).mean(1,dtype=np.float64).astype(np.float32)
  indices=np.arange(len(vals))*(1 if view=='full' else 64)
  ts=pd.Timestamp('1970-01-01')+pd.to_timedelta(indices*7812500,unit='ns')
  df=pd.DataFrame({'timestamp':ts.strftime('%Y-%m-%d %H:%M:%S.%f'),'ECG1':vals[:,0],'ECG2':vals[:,1]})
  for kind,text in public.items():
   t={'id':f'V020_100_131072_{view}_{kind}','question':text+(' Each row represents 64 consecutive original samples, all assigned the row value. Reconstruct by holding each row value for 64 samples: threshold sample counts must multiply qualifying rows by 64; contiguous run counts must not multiply. ' if view=='paa64' else ' Each row represents one original sample. ' )+' Use only raw_data values in the provided table. Order rows by timestamp when needed. Timestamps use an artificial relative-time origin 1970-01-01 and are not clinical acquisition dates. Output a single numeric value.', 'eval_metric':'rel_acc','ground_truth':answer(x,kind),'subtask':'V020 numeric ECG '+kind,'category':'Numeric ECG','view':view,'native':False,'raw_n':len(vals),'full_n':len(x),'kind':kind,'compressed_view_exact_answer':answer(np.repeat(vals,64,axis=0) if view=='paa64' else vals,kind)}
   make_db(t,df);unified.append(t)
 dump(OUT/'selection.json',{'native_ids':[t['id'] for t in native],'unified_ids':[t['id'] for t in unified],'rule':'Two lexicographically first native Global Aggregation tasks; reuse local files or fetch and hash-check only the two missing CSVs, then predefined six numeric queries on record100 middle-length context, full and PAA64 views. No model-outcome reselection.','adaptations':'Existing local Qwen3 backbone; independent SQLite loading preserving fractional seconds; official planner/generator/skills/executor/postprocessor unchanged.'})
 dump(OUT/'tasks.json',[dict(t,native=True) for t in native]+unified)
 print('Prepared',len(native),'native tasks and',len(unified),'unified tasks',flush=True)

def run():
 tasks=json.load(open(OUT/'tasks.json'));cfg=yaml.safe_load((OFFICIAL/'configs/online.yaml').read_text());ecfg=dict(cfg['executor'],shape_rules=cfg['shape_rules']);executor._RUNNER=ROOT/'experiments/v016-sonarts-qwen-local/traced_runner.py';official_execute=executor.execute;records=[]
 dump(OUT/'config.json',{'label':'Sonar-TS + local Qwen3-8B, v020 numeric ECG adapter','base_url':'http://127.0.0.1:8020/v1','dtype':'BF16','thinking':False,'temperature':0,'server_seed':None,'max_tokens':4096,'workers':1,'context':16384,'official_commit':'99866c43cd7ceb91a929de745e9f49cea92962e5','paid_api':False,'shape_rules':cfg['shape_rules']})
 for i,t in enumerate(tasks):
  case=OUT/'traces'/t['id'];case.mkdir(parents=True,exist_ok=True)
  if (case/'record.json').exists():records.append(json.load(open(case/'record.json')));continue
  if i==2 and not any(r['final_status']=='ok' for r in records[:2]):raise RuntimeError('Neither native smoke task executed successfully; halt unified pilot.')
  client=old.LocalClient('http://127.0.0.1:8020/v1',case);attempt=[0]
  def traced(code,tid,metric,**kwargs):
   k=attempt[0];attempt[0]+=1;(case/f'code-{k}.py').write_text(code);os.environ['V016_SQL_TRACE']=str(case/f'sql-{k}.jsonl.gz');os.environ['V016_OFFICIAL_RUNNER']=str(OFFICIAL/'sonar_ts/_runner.py');res=official_execute(code,tid,metric,**kwargs);dump(case/f'execution-{k}.json',dataclasses.asdict(res));return res
  executor.execute=traced;start=time.perf_counter();rec=pipeline.run_task(t,client,executor_config=ecfg);seconds=time.perf_counter()-start
  result=dataclasses.asdict(rec);score,_=evaluator.score_one('rel_acc',rec.prediction,t['ground_truth']);value=evaluator.parse_float(rec.prediction);truth=float(t['ground_truth']);correct=value is not None and abs(value-truth)<=.0005
  viewtruth=t.get('compressed_view_exact_answer',t['ground_truth']);view_correct=value is not None and abs(value-float(viewtruth))<=.0005
  result.update(native=t['native'],view=t.get('view','native'),kind=t.get('kind','native'),ground_truth=t['ground_truth'],compressed_view_exact_answer=viewtruth,official_relative_score=score,exact_numeric_correct=correct,view_numeric_correct=view_correct,wall_seconds=seconds,llm_seconds=sum(c['seconds'] for c in client.calls),llm_calls=len(client.calls),input_tokens=sum(c.get('response',{}).get('usage',{}).get('prompt_tokens',0) for c in client.calls),output_tokens=sum(c.get('response',{}).get('usage',{}).get('completion_tokens',0) for c in client.calls),code_failures=sum(x['status']!='ok' for x in rec.executor_log),code_retries=max(0,len(rec.code_attempts)-1))
  # Returned rows are not physical bytes read or scanned; preserve that distinction.
  queries=[];returned=0
  for log in case.glob('sql-*.jsonl.gz'):
   for line in gzip.open(log,'rt'):
    row=json.loads(line)
    if row['event']=='execute':queries.append(row['sql'])
    if row['event'] in ['fetchall','fetchmany']:returned+=row.get('n',0)
  result['sql_queries']=queries;result['sql_rows_returned']=returned;result['raw_scanned_bytes']='not established by SQL return tracing; no equality with broker logical reads claimed'
  dump(case/'record.json',result);records.append(result);dump(OUT/'records.json',records);print(json.dumps({k:result[k] for k in ['task_id','final_status','exact_numeric_correct','view_numeric_correct','wall_seconds','llm_calls']}),flush=True)
 dump(OUT/'complete.json',{'complete':True,'n':len(records)})
if __name__=='__main__':
 if sys.argv[-1]=='prepare':prepare()
 else:run()
