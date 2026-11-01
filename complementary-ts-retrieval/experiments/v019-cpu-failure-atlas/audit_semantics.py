"""Post-hoc label/source semantics audit; never imported by the prediction runner."""
from run import *
from collections import Counter

def main():
    ts=[t for t in read(VENDOR/'nlqtsbench/tasks.json') if t['subtask']=='Composite Trend']
    records=[]
    for t in ts:
        meta=t['meta'];p=parse_question(t)
        ordered=sorted(meta['all_injections'],key=lambda x:x['rank'])
        gt=set(t['ground_truth'])
        record={'id':t['id'],'rank_axis_metadata':meta['rank_axis'],'public_target_kind':p['target_kind'],'public_target_index':p['target_index'],'metadata_target_index':meta['rank_target_idx'],'public_kinds':p['kinds'],'public_superlative':p['sup'],'metadata_direction':meta['rank_direction'],'label_equals_metadata_topk':gt==set(meta['top_k']),'label_equals_first_five_injection_ranks':gt=={x['date'] for x in ordered[:5]},'injection_count':len(ordered),'injection_intensities_first_last':[ordered[0]['intensity'],ordered[-1]['intensity']],'repeated_kinds':len(set(p['kinds']))<len(p['kinds'])}
        records.append(record)
    # Analytical unit check: a linear ramp must include every increment in its run.
    code=re.search(r'```python\n(.*?)```',(VENDOR/'sonar_ts/skills/library/composite-trend-topk.md').read_text(),re.S).group(1)
    functions=code[code.index('def longest_run('):code.index('\nper_day = []')]
    e={'np':np,'pd':pd};exec(functions,e)
    v=np.arange(8,dtype=float);sm=pd.Series(v).rolling(4,center=True).mean().bfill().ffill().values
    a,b=e['longest_run'](np.diff(sm)>0)
    test={'raw':v.tolist(),'smoothed':sm.tolist(),'diff_run_inclusive_indices':[a,b],'released_amplitude':e['day_metric'](v,'rise'),'amplitude_including_last_increment':float(sm[b+1]-sm[a]),'explanation':'diff[i] = sm[i+1]-sm[i]; a..b increments span sm[a]..sm[b+1]. No benchmark labels used.'}
    dump(OUT/'semantic-audit.json',{'n':len(ts),'rank_axes':dict(Counter(x['rank_axis_metadata'] for x in records)),'label_equals_metadata_topk_count':sum(x['label_equals_metadata_topk'] for x in records),'label_equals_first_five_injection_ranks_count':sum(x['label_equals_first_five_injection_ranks'] for x in records),'repeated_kinds_count':sum(x['repeated_kinds'] for x in records),'public_target_index_mismatch_count':sum(x['public_target_index']!=x['metadata_target_index'] for x in records),'endpoint_unit_test':test,'records':records})
    print('Semantic audit:',len(ts),'tasks; endpoint example:',test,flush=True)

if __name__=='__main__':main()
