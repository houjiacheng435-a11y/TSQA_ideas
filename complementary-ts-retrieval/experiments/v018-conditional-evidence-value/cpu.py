"""Family-grouped CPU comparisons; test outcomes never tune a baseline."""
import collections
import gzip
import json
from pathlib import Path
import time
import numpy as np
from core import *

HERE=Path(__file__).parent;OUT=HERE.parents[1]/'results/v018-conditional-evidence-value'


def main():
    assert json.loads((OUT/'audit.complete.json').read_text())['gpu_gate_passed']
    assert not (OUT/'cpu.complete.json').exists()
    fs={f['id']:f for f in json.loads((OUT/'families-private.json').read_text())}
    es=[json.loads(s) for s in gzip.open(OUT/'episodes-private.jsonl.gz','rt')]
    # Tune just the diversity coefficient, exclusively on development families.
    dev=[e for e in es if fs[e['family']]['split']=='development']
    tuning=[]
    for lam in [.25,.5,.75,1.]:
        vals=[simulate(fs[e['family']],e,'mmr',e['depth']+1,lam)['state']['sufficient'] for e in dev]
        tuning.append({'lambda':lam,'development_sufficiency':sum(vals)/len(vals)})
    lam=max(tuning,key=lambda r:(r['development_sufficiency'],r['lambda']))['lambda']
    save(OUT/'development-selection.json',{'mmr_grid':tuning,'chosen_lambda':lam,'test_labels_used':False})
    methods=json.loads((OUT/'protocol.json').read_text())['baselines']
    sums=collections.defaultdict(lambda:np.zeros(7));pairs=collections.defaultdict(dict)
    begin=time.monotonic();rows=0
    with gzip.open(OUT/'cpu-trajectories.jsonl.gz','wt') as out:
        for j,e in enumerate(es):
            f=fs[e['family']];truth='YES' if e['ys'][e['source']]==0 else 'NO'
            for budget in [1,2,3]:
                for method in methods:
                    r=simulate(f,e,method,budget,lam);state=r['state'];p=state['posterior_yes']
                    assert not state['sufficient'] or state['answer']==truth
                    count=sum(a['matches_source'] and a['kind'] in required(e['depth']) for a in r['actions'])
                    mpred='YES' if p>=.5 else 'NO'
                    r.update({'truth':truth,'depth':e['depth'],'visibility':e['visibility'],'proxy':e['proxy'],
                        'source':e['source'],'mapping':e['mapping'],'ys':e['ys'],
                        'necessary_fraction':count/(e['depth']+1),'map_correct':mpred==truth,
                        'expected_map_accuracy':max(p,1-p)})
                    out.write(json.dumps(r,separators=(',',':'))+'\n');rows+=1
                    key=(e['family'],e['depth'],e['visibility'],e['proxy'],method,budget)
                    sums[key]+=np.array([1.,state['sufficient'],r['necessary_fraction'],state['answer']==truth,r['cost'],mpred==truth,max(p,1-p)])
                    if e['visibility']=='clear' and budget==e['depth']+1:
                        b=Broker(f,e,budget);vs={x['id']:public_value(b,x,budget) for x in b.index};top=max(vs.values())
                        opt={k for k,v in vs.items() if abs(v-top)<1e-8}
                        pk=(e['family'],e['depth'],tuple(e['ys']),e['proxy'],method,budget)
                        pairs[pk][e['source']]={'id':r['selected'][0],'optimal':r['selected'][0] in opt}
            if (j+1)%144==0:
                print(json.dumps({'episodes':j+1,'total':len(es),'rows':rows,'seconds':round(time.monotonic()-begin,1)}),flush=True)
    family_rows=[]
    for key,v in sums.items():
        family,depth,vis,proxy,method,budget=key
        family_rows.append({'family':family,'seed':fs[family]['seed'],'split':fs[family]['split'],
            'depth':depth,'visibility':vis,'proxy':proxy,'method':method,'budget':budget,'n':int(v[0]),
            'sufficiency_rate':v[1]/v[0],'necessary_fraction':v[2]/v[0],'numeric_answer_accuracy':v[3]/v[0],
            'mean_cost':v[4]/v[0],'map_accuracy':v[5]/v[0],'expected_map_accuracy':v[6]/v[0],
            'false_sufficiency_rate':0.,'sufficiency_judgment_accuracy':1.})
    save(OUT/'family-metrics.json',family_rows)
    flip=collections.defaultdict(lambda:[0,0])
    for key,x in pairs.items():
        family,depth,ys,proxy,method,budget=key
        assert set(x)=={0,1}
        val=x[0]['optimal'] and x[1]['optimal'] and x[0]['id']!=x[1]['id']
        dest=(family,depth,proxy,method,budget);flip[dest][0]+=int(val);flip[dest][1]+=1
    save(OUT/'conditional-action-flips.json',[dict(zip(['family','depth','proxy','method','budget'],k),correct=v[0],n=v[1]) for k,v in flip.items()])
    test=[r for r in family_rows if r['split']=='test'];groups=collections.defaultdict(list)
    for r in test:groups[(r['depth'],r['visibility'],r['proxy'],r['method'],r['budget'])].append(r)
    summary=[]
    rng=np.random.default_rng(181818)
    # Every group has the same 48 test families: stratified family bootstrap.
    inds=np.concatenate([rng.integers(16*k,16*(k+1),size=(2000,16)) for k in range(3)],axis=1)
    for key,x in groups.items():
        x=sorted(x,key=lambda r:(r['seed'],r['family']));assert len(x)==48
        row=dict(zip(['depth','visibility','proxy','method','budget'],key));row['families']=48
        for metric in ['sufficiency_rate','necessary_fraction','numeric_answer_accuracy','mean_cost','map_accuracy','expected_map_accuracy']:
            v=np.array([r[metric] for r in x]);means=v[inds].mean(axis=1)
            row[metric]={'mean':float(v.mean()),'family_bootstrap_95':np.quantile(means,[.025,.975]).tolist()}
        summary.append(row)
    save(OUT/'cpu-test-summary.json',summary)
    save(OUT/'cpu.complete.json',{'complete':True,'episodes':len(es),'trajectories':rows,
        'seconds':time.monotonic()-begin,'mmr_lambda':lam,'family_count':96,'test_families':48,
        'stopping_note':'All CPU policies use the same exact public posterior to stop; FSR=0 and sufficiency accuracy=1 are supplied-rule behavior, not learned capacity.'})
    print(json.dumps({'complete':True,'rows':rows,'seconds':time.monotonic()-begin}),flush=True)


if __name__=='__main__':main()
