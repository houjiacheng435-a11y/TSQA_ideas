"""Four preselected illustrative CPU executions; no model calls."""
import run as r
from run import np,pd,re,json,sqlite3,time

def main():
    protocol=r.read(r.HERE/'extension_protocol.json')
    tasks={x['id']:x for x in r.read(r.VENDOR/'nlqtsbench/tasks.json')}
    public=[{k:tasks[i][k] for k in ['id','question','channel','ts_data_path']} for i in protocol['ids']]
    labels=[{'id':i,'ground_truth':tasks[i]['ground_truth']} for i in protocol['ids']]
    # Separate evaluation-only fields before executing any detector.
    r.OUT=r.OUT/'extension';r.dump(r.OUT/'public-inputs.json',public);r.dump(r.OUT/'evaluation-only.json',labels)
    r.acquire()
    paths={x['id']:r.ROOT/x['path'] for x in r.read(r.OUT/'raw-manifest.json')}
    offline=r.loadmod('off','sonar_ts/offline.py');results=[]
    for t in public:
        raw=pd.read_csv(paths[t['id']]);raw['timestamp']=pd.to_datetime(raw.timestamp);ch=str(t['channel']);q=t['question']
        conn=sqlite3.connect(':memory:');conn.create_function('REGEXP',2,lambda pattern,value:int(bool(re.search(pattern,value or ''))))
        db=raw.copy();db.timestamp=raw.timestamp.dt.strftime('%Y-%m-%d %H:%M:%S');db.to_sql('raw_data',conn,index=False)
        shape='Shape_Identification' in t['id'];name='shape-identification' if shape else 'causal-anomaly-correlation'
        skill=f'sonar_ts/skills/library/{name}.md'
        code=re.search(r'```python\n(.*?)```',(r.VENDOR/skill).read_text(),re.S).group(1)
        if shape:
            window=re.search(r'within \[(.*?) to (.*?)\]',q).groups()
            p={'CH':ch,'SHAPE':'depression' if 'low plateau' in q else 'step_up','SEARCH_START':window[0],'SEARCH_END':window[1]}
            long=pd.DataFrame({'timestamp':raw.timestamp,'channel_id':ch,'value':raw[ch]})
            feat=offline.compute_features_for_view(long,freq='1D',resample_rule='1h',alphabet=list('abcde'),breakpoints=offline.generate_breakpoints(5));feat.to_sql('daily_feature',conn,index=False)
        else:
            up,down=re.search(r'channel (\S+) is the upstream source of channel (\S+),',q).groups()
            p={'UP':up,'DOWN':down,'YEAR':int(re.search(r'time period in (\d{4})',q).group(1))}
        for key,value in p.items():code=re.sub(r'^'+key+r'\s*=.*$',key+' = '+repr(value),code,flags=re.M)
        code='# Reconstructed from released skill; public parameters substituted.\n'+code
        if not shape:code=code.replace('# 3. Last-resort fallback.','# 3. Last-resort fallback.\nfallback_triggered = best is None')
        arms={}
        for arm in (['released_template','full_public_window'] if shape else ['released_template']):
            executable=code if arm=='released_template' else code.replace('if cand_days:\n','cand_days = []  # CPU intervention: force full public window\nif cand_days:\n',1)
            sql=[];conn.set_trace_callback(sql.append);env={'conn':conn,'np':np,'pd':pd,'question':q};start=time.monotonic();exec(executable,env)
            arms[arm]={'prediction':env['_result'],'raw_points':len(env['df']),'raw_start':str(env['df'].timestamp.min()),'raw_end':str(env['df'].timestamp.max()),'cpu_seconds':time.monotonic()-start,'sql':sql,'candidate_days':[str(d) for d in env.get('cand_days',[])],'last_resort_fallback':env.get('fallback_triggered')}
            path=r.OUT/'executed-code'/f'{t["id"]}-{arm}.py';path.parent.mkdir(exist_ok=True);path.write_text(executable)
        results.append({'id':t['id'],'skill':skill,'parameters':p,'arms':arms})
        conn.close();print('extension executed',t['id'],flush=True)
    r.dump(r.OUT/'cpu-results.json',results)
    ev=r.loadmod('ev','sonar_ts/evaluator.py');labs={t['id']:t for t in labels};published={x['task_id']:x for x in r.read(r.VENDOR/'output/per_task.json')}
    scores=[]
    for z in results:
        i=z['id'];scores.append({'id':i,'published_prediction':published[i]['prediction'],'ground_truth':labs[i]['ground_truth'],'published_iou':published[i]['score'],'cpu_arms':{a:{'prediction':d['prediction'],'iou':ev.score_one('iou',d['prediction'],labs[i]['ground_truth'])[0],'raw_points':d['raw_points'],'last_resort_fallback':d['last_resort_fallback']} for a,d in z['arms'].items()}})
    r.dump(r.OUT/'scores.json',scores)
    print(json.dumps(scores,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
