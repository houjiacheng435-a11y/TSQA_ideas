"""Post-discovery version-control diagnostic, NOT a tuned replacement arm.
The published output files predate the current CT skill. Execute the template
from their own last-change commit on exactly the original 12 frozen cases.
"""
from run import *

def main():
    commit='f2d61852498f1e406effc9d2696c512d2b3a2180';name='sonar_ts/skills/library/composite-trend-topk.md'
    source=subprocess.check_output(['git','show',f'{commit}:{name}'],cwd=VENDOR).decode()
    code=re.findall(r'```python\n(.*?)```',source,re.S)[-1]
    dump(OUT/'version-diagnostic-protocol.json',{'reason':'Git history shows result JSON last changed May 27, CT template changed June 2. Added this source-version diagnostic after primary interventions, not selected by outcome.','commit':commit,'path':name,'source_sha256':hashlib.sha256(source.encode()).hexdigest(),'cases':PROTOCOL['ids'],'alterations':'Only CH, YEAR, pattern_phrase substituted from public question. np,pd,question supplied in globals; no threshold edits. Reads full year as its own released code specifies.'})
    rawpaths={x['id']:ROOT/x['path'] for x in read(OUT/'raw-manifest.json')};results=[]
    for t in read(OUT/'public-inputs.json'):
        p=parse_question(t);conn=sqlite3.connect(':memory:');conn.create_function('REGEXP',2,lambda pat,val:int(bool(re.search(pat,val or ''))))
        raw=pd.read_csv(rawpaths[t['id']]);raw.to_sql('raw_data',conn,index=False)
        feat=pd.read_csv(OUT/'daily-features'/f'{t["id"]}.csv');feat.to_sql('daily_feature',conn,index=False)
        c=code
        for key,value in {'CH':p['CH'],'YEAR':p['YEAR'],'pattern_phrase':re.search(r"trend pattern '([^']+)'",t['question']).group(1)}.items():c=re.sub(r'^'+key+r'\s*=.*$',key+' = '+repr(value),c,flags=re.M)
        sql=[];conn.set_trace_callback(sql.append);env={'conn':conn,'np':np,'pd':pd,'question':t['question']};exec(c,env)
        results.append({'id':t['id'],'prediction':env['_result'],'sax_candidate_days':sorted(str(d) for d in env['sax_dates']),'raw_points':len(env['year_df']),'floor':env['floor'],'sql':sql})
        path=OUT/'executed-code-legacy'/f'{t["id"]}.py';path.parent.mkdir(exist_ok=True);path.write_text(c);conn.close()
    dump(OUT/'legacy-template-results.json',results)
    labels={x['id']:x for x in read(OUT/'evaluation-only.json')};ev=loadmod('ev','sonar_ts/evaluator.py');scores=[]
    for z in results:
        l=labels[z['id']];scores.append({'id':z['id'],'set_f1':ev.score_one('set_f1',z['prediction'],l['ground_truth'])[0],'published_set_match':set(z['prediction'])==ev.parse_date_set(l['published_prediction'])})
    dump(OUT/'legacy-template-scores.json',scores);print(json.dumps(scores,indent=2))

if __name__=='__main__':main()
