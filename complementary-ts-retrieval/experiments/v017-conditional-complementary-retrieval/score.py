"""Separate retrieval, supplied numerical stopping, and raw Qwen judgments."""
import collections
import gzip
import hashlib
import json
from pathlib import Path
from task import dump,policy,verify

OUT=Path(__file__).resolve().parents[2]/'results/v017-conditional-complementary-retrieval'


def pairs(records,answer_field):
    index={(r['family'],r['ai'],r['bi'],r['visible'],r.get('rotation',0)):r for r in records if r['ai']<2 and r['bi']<2}
    results=[]
    for (f,a,b,v,rot),r in index.items():
        for axis in ['ai','bi']:
            if (a if axis=='ai' else b)!=0:continue
            other=index[(f,1 if axis=='ai' else a,1 if axis=='bi' else b,v,rot)]
            x=r[answer_field];y=other[answer_field]
            results.append(x==r['world_answer'] and y==other['world_answer'] and x!=y)
    return {'n_pairs':len(results),'both_correct_and_flip':sum(results),'rate':sum(results)/len(results) if results else None}


def qmetrics(judgments):
    valid=[j for j in judgments if isinstance(j['parsed'],dict) and type(j['parsed'].get('sufficient')) is bool]
    insuff=[j for j in judgments if not j['numeric']['sufficient']]
    suff=[j for j in judgments if j['numeric']['sufficient']]
    def correct(j):return j in valid and j['parsed']['sufficient']==j['numeric']['sufficient']
    sensitiv=sum(correct(j) for j in suff)/len(suff) if suff else None
    specific=sum(correct(j) for j in insuff)/len(insuff) if insuff else None
    return {'n':len(judgments),'valid':len(valid),
        'sufficiency_accuracy':sum(correct(j) for j in judgments)/len(judgments),
        'sufficiency_accuracy_macro':(sensitiv+specific)/2 if suff and insuff else None,
        'false_sufficiency_count':sum(j in valid and j['parsed']['sufficient'] for j in insuff),
        'false_sufficiency_denominator':len(insuff),
        'false_sufficiency_rate':sum(j in valid and j['parsed']['sufficient'] for j in insuff)/len(insuff) if insuff else None,
        'answer_accuracy_when_evidence_sufficient':sum(j in valid and j['parsed'].get('answer')==j['numeric']['answer'] for j in suff)/len(suff) if suff else None}


def main():
    episodes=json.loads((OUT/'episodes-private.json').read_text());byid={e['id']:e for e in episodes}
    cpu=json.loads((OUT/'cpu-trajectories.json').read_text())
    pair_results=[]
    for method in ['independent_topk','coverage','state_rule','oracle']:
        for budget in [1,2]:
            xs=[]
            for r in cpu:
                if r['method']==method and r['budget']==budget:
                    e=byid[r['episode_id']];xs.append({**r,**{k:e[k] for k in ['ai','bi','visible','rotation']}})
            pair_results.append({'method':method,'budget':budget,**pairs(xs,'answer')})
    rs=json.loads((OUT/'controls/records.json').read_text())
    precheck=[json.loads(p.read_text()) for p in sorted((OUT/'pilot').glob('*/complete.json'))]
    pilot_summary=[]
    for method in ['independent_topk','coverage','state_rule','oracle']:
        xs=[]
        for r in rs:
            e=byid[r['episode_id']]
            t=policy(e,method,2)
            xs.append({'family':e['family'],'ai':e['ai'],'bi':e['bi'],'visible':e['visible'],
                       'world_answer':e['answer'],'pred':t['numeric']['answer'],'t':t,'e':e})
        need=[x for x in xs if not x['e']['initial_sufficient']]
        steps=[]
        for x in xs:
            e=x['e'];t=x['t']
            if e['initial_sufficient']:steps.append(0)
            else:
                reached=next((i+1 for i,event in enumerate(t['events']) if event['numeric_state']['sufficient']),None)
                if reached is not None:steps.append(reached)
        pilot_summary.append({'method':method,'budget':2,'n':len(xs),
            'complement_success_count':sum(x['t']['numeric']['sufficient'] for x in need),'complement_denominator':len(need),
            'numeric_answer_accuracy':sum(x['pred']==x['world_answer'] for x in xs)/len(xs),
            'mean_fetches':sum(x['t']['retrievals'] for x in xs)/len(xs),
            'mean_fetches_to_sufficiency_among_successes':sum(steps)/len(steps) if steps else None,
            'sufficiency_reached_n':len(steps),'counterfactual':pairs(xs,'pred')})
    allj=[j for r in rs for j in r['qwen_judgments']]
    finalrows=[]
    for r in rs:
        j=r['qwen_judgments'][-1]
        finalrows.append({**r,'world_answer':r['answer'],
                          'pred':j['parsed'].get('answer') if isinstance(j['parsed'],dict) else None})
    calls=[]
    for p in (OUT/'controls').glob('*/llm-calls.jsonl'):calls.extend(json.loads(s) for s in p.read_text().splitlines())
    pre_calls=[]
    for p in (OUT/'pilot').glob('*/llm-calls.jsonl'):pre_calls.extend(json.loads(s) for s in p.read_text().splitlines())
    summary={'cpu_counterfactual':pair_results,'pilot_retrieval':pilot_summary,
        'qwen_judgments':{'all_states':qmetrics(allj),
            'initial':qmetrics([r['qwen_judgments'][0] for r in rs]),
            'retrieved':qmetrics([r['qwen_judgments'][-1] for r in rs]),
            'counterfactual_final_answer':pairs(finalrows,'pred')},
        'adapter_status':'Excluded as an unfair/incomplete Sonar-TS adaptation; diagnostics only, not a valid method-performance row.',
        'adapter_precheck_complete_episodes':len(precheck),
        'adapter_precheck_regenerations':sum(len(r['attempts'])-1 for r in precheck),
        'adapter_precheck_completed_calls':sum('response' in c for c in pre_calls),
        'adapter_precheck_interrupted_calls':sum('response' not in c for c in pre_calls),
        'llm_calls':len(calls),'input_tokens':sum(c['response']['usage']['prompt_tokens'] for c in calls),
        'output_tokens':sum(c['response']['usage']['completion_tokens'] for c in calls),
        'llm_seconds':sum(c['seconds'] for c in calls),
        'truncations':sum(c['response']['choices'][0]['finish_reason']!='stop' for c in calls),
        'claim_limit':'CPU stopping uses supplied exact rules; adapter is not original Sonar-TS; no result proves a novel irreducible complementary-retrieval defect.'}
    # Strict tool boundary/provenance checks on every observed retrieval.
    for r in rs:
        e=byid[r['episode_id']];pool={p['id']:p for p in e['pool']}
        assert len(r['retrieval']['selected'])<=2
        for event in r['retrieval']['events']:assert event['obtained']==pool[event['candidate_id']]
        assert r['retrieval']['numeric']==verify(e['public'],r['retrieval']['evidence'])
    # Read-only fixed-program audit: raw access is a separate fact from scoring.
    oldtasks={t['id']:t for t in json.loads((OUT.parent/'v016-sonarts-qwen-local/tasks-selected.json').read_text())}
    fixed=[]
    for result in json.loads((OUT/'fixed-v016/summary.json').read_text()):
        rec=dict(result);seen=set();query_rows=[]
        for line in gzip.open(OUT/'fixed-v016'/rec['id']/'sql.jsonl.gz','rt'):
            event=json.loads(line)
            if event['event']=='fetchall':
                query_rows.append(event['n'])
                if 'raw_data' in event.get('sql','') and 'timestamp' in event.get('columns',[]):
                    i=event['columns'].index('timestamp');seen.update(str(x[i])[:10] for x in event['rows'])
        rec['query_row_counts']=query_rows
        if 'Composite' in rec['id']:
            t=oldtasks[rec['id']];gt=t.get('ground_truth',t.get('answer'))
            rec['reference_dates_fetched']=len(set(gt)&seen)
        fixed.append(rec)
    dump(OUT/'fixed-v016-access-audit.json',fixed)
    dump(OUT/'scores.json',summary)
    dump(OUT/'complete.json',{'complete':True,'pilot_episodes':20,'llm_calls':len(calls),'boundary_and_numeric_state_checks':True,
        'sonar_comparison_completed':False,'reason':'Precheck revealed non-equivalent runtime and placeholder generated programs; no comparative failure claim.'})
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
