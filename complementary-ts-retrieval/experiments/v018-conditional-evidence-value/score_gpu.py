"""Family-level model estimates, CF/conditional actions, separated tool/reader errors."""
import collections
import json
from pathlib import Path
import numpy as np
from core import *

HERE=Path(__file__).parent;OUT=HERE.parents[1]/'results/v018-conditional-evidence-value'


def summarize_agents(rows,fs):
    by=collections.defaultdict(list)
    for r in rows:by[(r['episode']['depth'],r['episode']['visibility'])].append(r)
    result=[]
    rng=np.random.default_rng(188188)
    ids=[f['id'] for f in sorted(fs.values(),key=lambda f:(f['seed'],f['id'])) if f['split']=='test']
    inds=np.concatenate([rng.integers(k*16,(k+1)*16,size=(2000,16)) for k in range(3)],axis=1)
    for (depth,vis),xs in by.items():
        vals={fid:np.zeros(15) for fid in ids};flip=collections.defaultdict(dict);cf=collections.defaultdict(dict)
        for r in xs:
            e=r['episode'];v=vals[e['family']];v[0]+=1;v[1]+=r['final_numeric']['sufficient']
            v[2]+=r['prediction']==r['truth'];v[3]+=r['prediction']==r['truth'] and r['final_numeric']['sufficient'];v[4]+=r['cost']
            v[5]+=len(set(required(depth))&set(r['final_numeric']['observations']))/(depth+1)
            for d in r['decisions']:
                obj=d['parsed'];actual=d['numeric_state_before']['sufficient'];valid=isinstance(obj,dict) and type(obj.get('sufficient')) is bool
                v[6]+=1;v[7]+=not actual
                v[8]+=valid and obj['sufficient'] and not actual
                v[9]+=valid and obj['sufficient']==actual
                v[10]+=valid and obj.get('action')=='STOP' and obj.get('answer') in ['YES','NO'] and not actual
                v[11]+=actual;v[12]+=valid and not obj['sufficient'] and actual
                v[13]+=valid and obj.get('action')=='FETCH' and actual
            v[14]+=r['status']!='stopped'
            cf[(e['family'],e['source'],vis)][e['ys'][e['source']]]=r['prediction']
            if vis=='clear':
                b=Broker(fs[e['family']],e,3);obj=r['decisions'][0]['parsed']
                cid=obj.get('id') if isinstance(obj,dict) else None
                item=b.records.get(cid)
                good=bool(item and item['bundle_number']==b.known_group and item['kind'] in required(depth))
                flip[(e['family'],tuple(e['ys']))][e['source']]={'good':good,'id':cid}
        arr=np.array([vals[i] for i in ids]);point=arr.sum(0);boot=arr[inds].sum(axis=1)
        def ratio(a,b):
            z=np.divide(boot[:,a],boot[:,b],out=np.zeros(2000),where=boot[:,b]>0)
            return {'value':float(point[a]/point[b]) if point[b] else None,
                    'family_bootstrap_95':np.quantile(z,[.025,.975]).tolist() if point[b] else None,
                    'numerator':float(point[a]),'denominator':float(point[b])}
        rec={'depth':depth,'visibility':vis,'n':len(xs),'families':48,
             'retrieval_sufficiency':ratio(1,0),'answer_accuracy':ratio(2,0),'grounded_answer_accuracy':ratio(3,0),
             'mean_cost':ratio(4,0),'necessary_fraction':ratio(5,0),
             'sufficiency_accuracy':ratio(9,6),'false_sufficiency_rate':ratio(8,7),
             'false_answer_stop_rate':ratio(10,7),'false_insufficiency_rate':ratio(12,11),
             'continued_fetch_after_sufficient':ratio(13,11),'interface_failure_rate':ratio(14,0)}
        cvals=[p.get(0)=='YES' and p.get(1)=='NO' for p in cf.values()]
        rec['counterfactual_both_correct']={'correct':sum(cvals),'n':len(cvals),'rate':sum(cvals)/len(cvals)}
        if any(set(p)=={0,1} for p in flip.values()):
            z=[p[0]['good'] and p[1]['good'] and p[0]['id']!=p[1]['id'] for p in flip.values() if set(p)=={0,1}]
            rec['cost_efficient_conditional_action_flip']={'correct':sum(z),'n':len(z),'rate':sum(z)/len(z)}
        else:rec['cost_efficient_conditional_action_flip']=None
        result.append(rec)
    return result


def reader_scores(rows):
    groups=collections.defaultdict(list)
    for r in rows:groups[(r['condition'],r['episode']['depth'])].append(r)
    out=[]
    for (condition,depth),xs in groups.items():
        parsed=[r for r in xs if isinstance(r['parsed'],dict) and r['parsed'].get('answer') in ['YES','NO','UNKNOWN']]
        counts=collections.Counter(r['parsed']['answer'] for r in parsed)
        fam=collections.defaultdict(list);pairs=collections.defaultdict(dict)
        for r in xs:
            answer=r['parsed'].get('answer') if isinstance(r['parsed'],dict) else None
            fam[r['episode']['family']].append(answer==r['truth'])
            pairs[r['episode']['family']][r['truth']]=answer
        v=np.array([sum(z)/len(z) for z in fam.values()]);rng=np.random.default_rng(18819)
        boot=v[rng.integers(0,len(v),size=(2000,len(v)))].mean(1)
        out.append({'condition':condition,'depth':depth,'n':len(xs),'families':len(fam),
            'parse_rate':len(parsed)/len(xs),'answer_accuracy':float(v.mean()),
            'family_bootstrap_95':np.quantile(boot,[.025,.975]).tolist(),'answer_distribution':dict(counts),
            'cf_pairs_both_correct':sum(p.get('YES')=='YES' and p.get('NO')=='NO' for p in pairs.values()),
            'cf_pairs':len(pairs)})
    return out


def main():
    fs={f['id']:f for f in json.loads((OUT/'families-private.json').read_text())}
    result={}
    for name in ['qwen-agents-schema','qwen-agents-documented','qwen-agents-neutral']:
        rs=json.loads((OUT/name/'records.json').read_text());assert len(rs)==(288 if name=='qwen-agents-neutral' else 960)
        expected={e['id'] for e in json.loads((OUT/('reader-episodes-private.json' if name=='qwen-agents-neutral' else 'gpu-episodes-private.json')).read_text())}
        assert {r['episode']['id'] for r in rs}==expected
        for r in rs:
            e=r['episode'];b=Broker(fs[e['family']],e,3)
            for d in r['decisions']:
                assert b.state()==d['numeric_state_before']
                if 'obtained' in d:assert b.fetch(d['parsed']['id'])==d['obtained']
            assert b.selected==r['selected'] and b.state()==r['final_numeric']
            if b.state()['sufficient']:assert b.state()['answer']==r['truth']
        result[name]=summarize_agents(rs,fs)
    matched_ids={e['id'] for e in json.loads((OUT/'reader-episodes-private.json').read_text())}
    result['matched_prompt_controls']={}
    for name in ['qwen-agents-schema','qwen-agents-documented','qwen-agents-neutral']:
        matched=[r for r in json.loads((OUT/name/'records.json').read_text()) if r['episode']['id'] in matched_ids]
        assert len(matched)==288
        result['matched_prompt_controls'][name]=summarize_agents(matched,fs)
    q=json.loads((OUT/'qwen-readers/records.json').read_text());assert len(q)==864
    a=json.loads((OUT/'chatts-readers/records.json').read_text());assert len(a)==576
    lag=json.loads((OUT/'qwen-lag-control/records.json').read_text());assert len(lag)==288
    result['qwen_readers']=reader_scores([r for r in q if r['condition']!='raw_first_action']+lag)
    result['chatts_readers']=reader_scores(a)
    routing=[]
    for condition in ['raw_first_action','facts_reference_first','facts_documented_first']:
        vals=[]
        if condition=='raw_first_action':items=[(r['episode'],r['parsed']) for r in q if r['condition']==condition]
        else:
            directory='qwen-agents-schema' if condition=='facts_reference_first' else 'qwen-agents-documented'
            allowed={r['episode']['id'] for r in q if r['condition']=='raw_first_action'}
            items=[(r['episode'],r['decisions'][0]['parsed']) for r in json.loads((OUT/directory/'records.json').read_text()) if r['episode']['id'] in allowed]
        for e,obj in items:
            b=Broker(fs[e['family']],e,3);item=b.records.get(obj.get('id')) if isinstance(obj,dict) else None
            vals.append({'family':e['family'],'depth':e['depth'],'correct_bundle':bool(item and item['bundle_number']==b.known_group),
                         'cost_efficient':bool(item and item['bundle_number']==b.known_group and item['kind'] in required(b.depth))})
        for d in [0,1,2]:
            x=[r for r in vals if r['depth']==d]
            routing.append({'condition':condition,'depth':d,'n':len(x),'correct_bundle':sum(r['correct_bundle'] for r in x)/len(x),'cost_efficient':sum(r['cost_efficient'] for r in x)/len(x)})
    result['raw_facts_first_action']=routing
    calls=[]
    for directory in ['qwen-agents-schema','qwen-agents-documented','qwen-agents-neutral','qwen-readers','qwen-lag-control']:
        for p in (OUT/directory).glob('*/calls.jsonl'):
            calls.extend(json.loads(s) for s in p.read_text().splitlines())
    result['efficiency']={'qwen_completed_calls':sum('response' in c for c in calls),
        'input_tokens':sum(c.get('response',{}).get('usage',{}).get('prompt_tokens',0) for c in calls),
        'output_tokens':sum(c.get('response',{}).get('usage',{}).get('completion_tokens',0) for c in calls),
        'truncations':sum(c['response']['choices'][0]['finish_reason']!='stop' for c in calls if 'response' in c),
        'chatts_calls':len(a),'chatts_truncations':sum(not r['stopped_on_eos'] for r in a),
        'chatts_peak_allocated_bytes':max(r['peak_allocated_bytes'] for r in a),
        'chatts_output_tokens':sum(len(r['tokens']) for r in a),
        'chatts_input_positions':sum(r['input_positions'] for r in a),
        'qwen_http_seconds_sum_including_queue':sum(c['seconds'] for c in calls if 'response' in c)}
    save(OUT/'gpu-scores.json',result)
    save(OUT/'complete.json',{'complete':True,'independent_test_families':48,'dynamic_episodes_per_condition':960,
        'supplementary_neutral_prompt_episodes':288,'qwen_corrected_lag_control_calls':288,'qwen_reader_and_first_action_calls':864,'chatts_reader_calls':576,'all_access_traces_replayed':True,
        'no_new_model_training':True})
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
