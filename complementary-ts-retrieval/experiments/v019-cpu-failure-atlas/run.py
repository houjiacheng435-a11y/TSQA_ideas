"""CPU-only, pinned-source audit. No model imports or API calls.
Run audit -> acquire -> run -> score. Raw observations and labels stay separate.
"""
from pathlib import Path
import concurrent.futures
import os
import argparse, csv, hashlib, importlib.util, json, re, sqlite3, subprocess, sys, time, urllib.request
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=Path(os.environ.get('V019_OUTPUT',str(ROOT/'results/v019-cpu-failure-atlas')))
PROTOCOL=json.loads((HERE/'protocol.json').read_text())
VENDOR=Path(os.environ.get('SONARTS_ROOT','/root/autodl-tmp/cf-run/vendor/Sonar-TS-v016-direct'))
REV=PROTOCOL['dataset_revision']

def dump(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    if path.exists():
        if path.read_bytes()!=raw: raise FileExistsError(f'Refuse to replace: {path}')
    else: path.write_bytes(raw)

def read(path): return json.loads(path.read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def loadmod(name,filename):
    spec=importlib.util.spec_from_file_location(name,VENDOR/filename)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def audit():
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=VENDOR,text=True).strip()
    assert commit==PROTOCOL['official_commit']
    sourcefiles=['output/per_task.json','output/summary.json','output/predict.json','nlqtsbench/tasks.json','sonar_ts/evaluator.py','sonar_ts/offline.py','configs/offline.yaml','sonar_ts/skills/library/composite-trend-topk.md']
    provenance=[]
    for f in sourcefiles:
        raw=(VENDOR/f).read_bytes()
        assert raw==subprocess.check_output(['git','show',f'{commit}:{f}'],cwd=VENDOR)
        provenance.append({'path':f,'sha256':sha(VENDOR/f),'git_blob':subprocess.check_output(['git','rev-parse',f'{commit}:{f}'],cwd=VENDOR,text=True).strip(),'last_commit':subprocess.check_output(['git','log','-1','--format=%H %cI','--',f],cwd=VENDOR,text=True).strip()})
    tasks=read(VENDOR/'nlqtsbench/tasks.json'); rows=read(VENDOR/'output/per_task.json');pred=read(VENDOR/'output/predict.json');ev=loadmod('ev','sonar_ts/evaluator.py')
    assert len(tasks)==len(rows)==len(pred)==1153
    errors=[];gt_errors=[];index_errors=[]
    for i,(t,r,p) in enumerate(zip(tasks,rows,pred)):
        if not(t['id']==r['task_id'] and i==r['id']==p['id'] and r['prediction']==p['prediction']): index_errors.append(i)
        s,_=ev.score_one(r['eval_metric'],r['prediction'],t['ground_truth'])
        s2,_=ev.score_one(r['eval_metric'],r['prediction'],r['ground_truth'])
        if abs(s-r['score'])>1e-10:errors.append({'id':t['id'],'published':r['score'],'rescored':s})
        if abs(s-s2)>1e-10:gt_errors.append(t['id'])
    stats={}
    for sub in sorted({r['subtask'] for r in rows}):
        rr=[r for r in rows if r['subtask']==sub];scores=np.array([r['score'] for r in rr]);entry=read(VENDOR/'output/summary.json')['by_subtask'][sub]
        assert abs(float(scores.mean())-entry['avg'])<1e-10
        stats[sub]={'n':len(rr),'metric':rr[0]['eval_metric'],'mean':float(scores.mean()),'median':float(np.median(scores)),'zero':int(sum(scores==0)),'partial':int(sum((scores>0)&(scores<1-1e-10))),'full':int(sum(scores>=1-1e-10)),'quartiles':np.quantile(scores,[.25,.5,.75]).tolist()}
    lookup={t['id']:t for t in tasks};rr={r['task_id']:r for r in rows}
    frozen=[]
    for predicate in [lambda s:s==0,lambda s:0<s<1,lambda s:s==1]:
        frozen += sorted([r['task_id'] for r in rows if r['subtask']=='Composite Trend' and predicate(r['score'])])[:4]
    assert frozen==PROTOCOL['ids']
    public=[{k:lookup[i][k] for k in ['id','question','channel','ts_data_path']} for i in frozen]
    dump(OUT/'public-inputs.json',public)
    dump(OUT/'evaluation-only.json',[{'id':i,'ground_truth':lookup[i]['ground_truth'],'published_prediction':rr[i]['prediction'],'published_score':rr[i]['score']} for i in frozen])
    categories=['Composite Trend','Shape Identification','Causal Anomaly']
    cat=[{'id':r['task_id'],'subtask':r['subtask'],'metric':r['eval_metric'],'published_score':r['score'],'published_prediction':r['prediction'],'ground_truth':lookup[r['task_id']]['ground_truth'],'question':lookup[r['task_id']]['question'],'channel':lookup[r['task_id']]['channel']} for r in rows if r['subtask'] in categories]
    dump(OUT/'official-case-catalog.json',cat)
    audit={'commit':commit,'protocol_sha256':sha(HERE/'protocol.json'),'sources':provenance,'n_rescored':len(rows),'score_mismatches':errors,'ground_truth_score_mismatches':gt_errors,'index_or_prediction_mismatches':index_errors,'distribution':stats,'runtime_config_for_published_predictions':'Not established by these result files; no per-case SQL or generated Python traces available in audited artifacts.'}
    dump(OUT/'official-audit.json',audit)
    print(json.dumps({'rescored':len(rows),'mismatches':len(errors),'target_distributions':{k:stats[k] for k in categories}},ensure_ascii=False),flush=True)

def acquire():
    catalog={x['path']:x for x in read(HERE/'raw-file-catalog.json')}
    def get_one(t):
        rel=t['ts_data_path'];item=catalog[rel];found=list((ROOT/'data').glob(f'**/{rel}'))
        path=found[0] if found else ROOT/'data/v019-cpu-failure-atlas'/rel
        if not path.exists():
            url=f'https://hf-mirror.com/datasets/mrtan/NLQTSBench/resolve/{REV}/{rel}'
            result=subprocess.run(['curl','-4','--noproxy','*','--location','--fail','--silent','--show-error','--connect-timeout','8','--max-time','90','--retry','2','--retry-all-errors',url],capture_output=True,check=True)
            raw=result.stdout
            assert len(raw)<=8_000_000
            path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as f:f.write(raw)
        raw=path.read_bytes();blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        assert len(raw)==item['size']
        if item.get('lfs'):assert hashlib.sha256(raw).hexdigest()==item['lfs']['oid']
        else:assert blob==item['oid']
        record={'id':t['id'],'path':str(path.relative_to(ROOT)),'bytes':len(raw),'sha256':sha(path),'upstream_git_blob':item['oid'],'upstream_lfs':item.get('lfs'),'dataset_revision':REV}
        print('verified CSV',t['id'],len(raw),flush=True)
        return record
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        records=list(pool.map(get_one,read(OUT/'public-inputs.json')))
    dump(OUT/'raw-manifest.json',records)

def parse_question(t):
    q=t['question'];pattern=re.search(r"trend pattern '([^']+)'",q).group(1)
    parts=pattern.split(', then ')
    target=re.search(r'where the (.*?) segment is the (.*?)\.',q)
    phrase,sup=target.groups();idx=[i for i,p in enumerate(parts) if p==phrase]
    assert len(idx)==1,(t['id'],parts,phrase)
    return dict(CH=str(t['channel']),YEAR=int(re.search(r'during (\d{4})',q).group(1)),kinds=[p.split()[-1] for p in parts],target_kind=phrase.split()[-1],target_adj=phrase.split()[0] if len(phrase.split())>1 else '',sup=sup.split()[0],target_index=idx[0])

def rank(metrics,descending,fixed_floor=None):
    if not metrics:return [],None
    floor=float(np.quantile([d['metric'] for d in metrics],.5 if descending else .8)) if fixed_floor is None else fixed_floor
    kept=[d for d in metrics if d['metric']>=floor] or metrics
    return sorted(kept,key=lambda d:d['metric'],reverse=descending)[:5],floor

def independent_day(v,kinds,target):
    # Exhaustive ordered piecewise OLS fit, min 4 observations per segment.
    # Objective sees only raw observations and requested kinds, never labels.
    n=len(v);m=len(kinds)
    if n<4*m:return None
    x=np.arange(n,dtype=float);N=n+1
    prefix=lambda a:np.r_[0.,np.cumsum(a)]
    px,py,pxx,pyy,pxy=map(prefix,[x,v,x*x,v*v,x*v])
    i=np.arange(N)[:,None];j=np.arange(N)[None,:];length=j-i
    den=np.maximum(length,1)
    sx=px[j]-px[i];sy=py[j]-py[i]
    sxx=pxx[j]-pxx[i]-sx*sx/den;syy=pyy[j]-pyy[i]-sy*sy/den;sxy=pxy[j]-pxy[i]-sx*sy/den
    slope=np.divide(sxy,sxx,out=np.zeros_like(sxy),where=sxx>1e-10)
    sse=np.maximum(syy-slope*sxy,0);sse[length<4]=np.inf
    dp=np.full((m+1,N),np.inf);dp[0,0]=0;back=np.full((m+1,N),-1,int)
    for k,kind in enumerate(kinds,1):
        cost=sse.copy()
        if kind=='rise':cost[slope<=0]=np.inf
        if kind=='fall':cost[slope>=0]=np.inf
        for end in range(4*k,n+1):
            scores=dp[k-1]+cost[:,end];best=int(np.argmin(scores))
            dp[k,end]=scores[best];back[k,end]=best
    if not np.isfinite(dp[m,n]):return None
    intervals=[];end=n
    for k in range(m,0,-1):
        start=int(back[k,end]);intervals.append((start,end));end=start
    intervals.reverse();a,b=intervals[target]
    metric=float(np.std(v[a:b])) if kinds[target]=='stable' else abs(float(slope[a,b]))
    return {'metric':metric,'segments':[list(z) for z in intervals],'fit_sse':float(dp[m,n]),'target_points':b-a}

def run():
    if (OUT/'cpu-results.json').exists(): raise FileExistsError('Use a fresh V019_OUTPUT directory for a new run')
    offline=loadmod('offline','sonar_ts/offline.py')
    code=re.search(r'```python\n(.*?)```',(VENDOR/'sonar_ts/skills/library/composite-trend-topk.md').read_text(),re.S).group(1)
    rawpaths={x['id']:ROOT/x['path'] for x in read(OUT/'raw-manifest.json')}
    allresults=[]
    for t in read(OUT/'public-inputs.json'):
        start=time.monotonic();p=parse_question(t);ch=p['CH'];raw=pd.read_csv(rawpaths[t['id']]);raw['timestamp']=pd.to_datetime(raw['timestamp'])
        assert ch in raw and raw['timestamp'].is_monotonic_increasing and not raw['timestamp'].duplicated().any()
        raw=raw[(raw.timestamp.dt.year==p['YEAR'])].copy();assert raw[ch].notna().all()
        long=pd.DataFrame({'timestamp':raw.timestamp,'channel_id':ch,'value':raw[ch]})
        feat=offline.compute_features_for_view(long,freq='1D',resample_rule='1h',alphabet=list('abcde'),breakpoints=offline.generate_breakpoints(5))
        conn=sqlite3.connect(':memory:');conn.create_function('REGEXP',2,lambda pattern,value:int(bool(re.search(pattern,value or ''))))
        featurelogs=OUT/'daily-features';featurelogs.mkdir(exist_ok=True);feat.to_csv(featurelogs/f'{t["id"]}.csv',index=False)
        rawcopy=raw.copy();rawcopy['timestamp']=raw.timestamp.dt.strftime('%Y-%m-%d %H:%M:%S');rawcopy.to_sql('raw_data',conn,index=False);feat.to_sql('daily_feature',conn,index=False)
        sql=[];conn.set_trace_callback(sql.append)
        substitutions={'CH':repr(ch),'YEAR':str(p['YEAR']),'kinds':repr(p['kinds']),'target_kind':repr(p['target_kind']),'target_adj':repr(p['target_adj']),'sup':repr(p['sup'])}
        executed=code
        for name,value in substitutions.items():executed=re.sub(r'^'+name+r'\s*=.*$',name+' = '+value,executed,flags=re.M)
        env={'conn':conn};exec(compile(executed,'released-composite-trend-template','exec'),env)
        assert env['CH']==ch
        direct=env['_result'];original_dates=[str(d) for d in env['cand_days']];pre_dates=sorted({str(pd.Timestamp(s).date()) for s in env['hits']['window_start']})
        descending=env['descending'];full=[];corrected=[];independent=[];daily=[]
        corrected_code=code[code.index('def day_metric('):code.index('\nper_day = []')].replace('sm[r[1]]','sm[r[1]+1]')
        fixedenv={'np':np,'pd':pd,'longest_run':env['longest_run']};exec(corrected_code,fixedenv)
        for date,sub in raw.groupby(raw.timestamp.dt.date):
            ds=str(date);v=sub[ch].to_numpy(dtype=float)
            a=env['day_metric'](v,p['target_kind']);b=fixedenv['day_metric'](v,p['target_kind']);c=independent_day(v,p['kinds'],p['target_index'])
            if a is not None:full.append({'date':ds,'metric':a})
            if b is not None:corrected.append({'date':ds,'metric':b})
            if c is not None:independent.append({'date':ds,**c})
            daily.append({'date':ds,'points':len(v),'official_metric':a,'endpoint_corrected_metric':b,'independent_fit':c})
        subset=[d for d in full if d['date'] in original_dates];ours,floor=rank(subset,descending)
        assert [d['date'] for d in ours]==direct
        arms={'released_template':direct}
        floors={'released_template':floor}
        for name,ms,ff in [('full_year',full,None),('full_year_frozen_floor',full,floor),('candidates_endpoint_corrected',[d for d in corrected if d['date'] in original_dates],None),('full_year_endpoint_corrected',corrected,None)]:
            vals,fl=rank(ms,descending,ff);arms[name]=[d['date'] for d in vals];floors[name]=fl
        arms['independent_piecewise']= [d['date'] for d in sorted(independent,key=lambda d:d['metric'],reverse=descending)[:5]]
        result={'id':t['id'],'parameters':p,'raw_points':len(raw),'full_days':raw.timestamp.dt.date.nunique(),'sax_regex':env['sax_regex'],'pre_fallback_candidates':pre_dates,'post_fallback_candidates':original_dates,'raw_access_days_released':original_dates,'raw_access_points_released':len(env['df']),'fallback':len(pre_dates)<5,'arms':arms,'floors':floors,'cpu_seconds':time.monotonic()-start}
        dump(OUT/'cases'/f'{t["id"]}.json',result);dump(OUT/'day-metrics'/f'{t["id"]}.json',daily);dump(OUT/'sql-traces'/f'{t["id"]}.json',sql)
        src=OUT/'executed-code'/f'{t["id"]}.py';src.parent.mkdir(exist_ok=True);src.write_text(executed)
        allresults.append(result);conn.close()
        print(json.dumps({'finished':t['id'],'seconds':round(result['cpu_seconds'],2),'candidates':len(original_dates),'fallback':result['fallback']}),flush=True)
    dump(OUT/'cpu-results.json',allresults)

def score():
    ev=loadmod('ev','sonar_ts/evaluator.py');labels={x['id']:x for x in read(OUT/'evaluation-only.json')};out=[]
    for r in read(OUT/'cpu-results.json'):
        gt=ev.parse_date_set(labels[r['id']]['ground_truth']);assert len(gt)==5
        rr={'id':r['id'],'published_score':labels[r['id']]['published_score'],'full_days':r['full_days'],'sax_candidates':len(r['pre_fallback_candidates']),'access_days':len(r['post_fallback_candidates']),'fallback':r['fallback'],'pre_fallback_gt_recall':len(gt & set(r['pre_fallback_candidates']))/len(gt),'post_fallback_gt_recall':len(gt & set(r['post_fallback_candidates']))/len(gt),'published_template_set_match':ev.parse_date_set(labels[r['id']]['published_prediction'])==set(r['arms']['released_template'])}
        for arm,pred in r['arms'].items():rr[arm]=ev.score_one('set_f1',pred,list(gt))[0]
        rr['candidate_f1_ceiling']=2*min(5,len(gt & set(r['post_fallback_candidates'])))/10
        out.append(rr)
    dump(OUT/'intervention-scores.json',out)
    table=pd.DataFrame(out);table.to_csv(OUT/'intervention-scores.csv',index=False)
    print(table.to_string(index=False),flush=True)
    print('Means (stratified cases only):',table.select_dtypes('number').mean().to_dict(),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['audit','acquire','run','score']);args=ap.parse_args();globals()[args.stage]()
