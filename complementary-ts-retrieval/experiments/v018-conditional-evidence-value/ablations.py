"""Supplementary tie and public-observability audits; not tuned test baselines.

Primary CPU comparisons remain frozen. These stronger controls explain why a
myopic failure is not evidence that learning or a new architecture is needed.
"""
import collections
import gzip
import json
from pathlib import Path
from core import *

HERE=Path(__file__).parent;OUT=HERE.parents[1]/'results/v018-conditional-evidence-value'


def supplemental(f,e,method,budget):
    b=Broker(f,e,budget)
    while not b.state()['sufficient'] and len(b.selected)<budget:
        avail=[x for x in b.index if x['id'] not in b.selected]
        pos={x['id']:i for i,x in enumerate(b.index)}
        if method=='public_certificate_optimal':
            outstanding=[k for k in required(b.depth) if k not in b.observations]
            if len(outstanding)>budget-len(b.selected):break
            # No hidden mapping: a first relevant-type probe is needed in blind mode.
            choices=[x for x in avail if x['kind'] in outstanding and (b.known_group is None or x['bundle_number']==b.known_group)]
            x=max(choices,key=lambda x:(priority(b,x),-pos[x['id']]))
        elif method=='lookahead2_index_tie':
            x=max(avail,key=lambda x:(round(public_value(b,x,min(2,budget-len(b.selected))),10),-pos[x['id']]))
        else:
            obs=tuple(sorted(b.observations.items()))
            def cert(x):
                if x['bundle_number']!=b.known_group:return 0.
                if x['kind'] not in required(b.depth) and x['kind']!='proxy':return 0.
                return round(sum(p*(h(b.depth,new)<1e-12) for p,new in outcomes(b.depth,obs,x['kind'])),10)
            if method=='marginal_sufficiency_index_tie':x=max(avail,key=lambda x:(cert(x),-pos[x['id']]))
            else:x=max(avail,key=lambda x:(cert(x),x['bundle_number']==b.known_group,priority(b,x),-pos[x['id']]))
        b.fetch(x['id'])
    return {'sufficiency':b.state()['sufficient'],'cost':len(b.selected)}


def main():
    fs={f['id']:f for f in json.loads((OUT/'families-private.json').read_text())}
    es=[json.loads(s) for s in gzip.open(OUT/'episodes-private.jsonl.gz','rt')]
    es=[e for e in es if fs[e['family']]['split']=='test']
    sums=collections.defaultdict(lambda:[0,0.,0.])
    for e in es:
        if e['visibility']=='clear':
            for method in ['marginal_sufficiency_index_tie','marginal_sufficiency_dependency_tie','lookahead2_index_tie']:
                r=supplemental(fs[e['family']],e,method,e['depth']+1)
                key=(e['family'],e['depth'],e['visibility'],e['proxy'],method,e['depth']+1)
                v=sums[key];v[0]+=1;v[1]+=r['sufficiency'];v[2]+=r['cost']
        for budget in [1,2,3]:
            r=supplemental(fs[e['family']],e,'public_certificate_optimal',budget)
            n=e['depth']+1
            bound=(1. if budget>=n else 0.) if e['visibility']=='clear' else (0. if budget<n else (.5 if budget==n else 1.))
            key=(e['family'],e['depth'],e['visibility'],e['proxy'],'public_certificate_optimal',budget)
            v=sums[key];v[0]+=1;v[1]+=r['sufficiency'];v[2]+=r['cost']
    rows=[]
    for key,v in sums.items():rows.append(dict(zip(['family','depth','visibility','proxy','method','budget'],key),n=v[0],sufficiency=v[1]/v[0],cost=v[2]/v[0]))
    grouped=collections.defaultdict(list)
    for r in rows:grouped[(r['depth'],r['visibility'],r['proxy'],r['method'],r['budget'])].append(r)
    summary=[]
    for key,x in grouped.items():
        assert len(x)==48
        row=dict(zip(['depth','visibility','proxy','method','budget'],key))
        row.update(sufficiency=sum(r['sufficiency'] for r in x)/48,mean_cost=sum(r['cost'] for r in x)/48,families=48)
        if row['method']=='public_certificate_optimal':
            n=row['depth']+1;b=row['budget']
            bound=(1. if b>=n else 0.) if row['visibility']=='clear' else (0. if b<n else (.5 if b==n else 1.))
            assert abs(row['sufficiency']-bound)<1e-12
            row['public_success_upper_bound']=bound
        summary.append(row)
    save(OUT/'supplementary-ablations.json',{'scope':'Supplementary after primary CPU results; no main baseline replaced or tuned.',
        'definition':'Marginal-certainty ties and horizon ties reported explicitly. Public certificate-optimal uses no hidden mapping; it abstains if the remaining budget cannot complete a certificate.',
        'family_metrics':rows,'summary':summary})
    save(OUT/'supplementary.complete.json',{'complete':True,'public_bounds_exactly_matched':True,'test_families':48})
    print('Supplementary tie and public upper-bound audit passed.')


if __name__=='__main__':main()
