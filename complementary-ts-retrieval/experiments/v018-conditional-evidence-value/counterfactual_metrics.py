"""Score paired target-label interventions, keeping other context's label fixed."""
import collections
import gzip
import json
from pathlib import Path
import numpy as np
from core import save

HERE=Path(__file__).parent;OUT=HERE.parents[1]/'results/v018-conditional-evidence-value'


def main():
    pairs=collections.defaultdict(dict)
    with gzip.open(OUT/'cpu-trajectories.jsonl.gz','rt') as f:
        for line in f:
            r=json.loads(line)
            if '-test-' not in r['family']:continue
            s=r['source'];key=(r['family'],r['depth'],r['visibility'],r['proxy'],r['method'],r['budget'],s,r['mapping'],r['ys'][1-s])
            pairs[key][r['ys'][s]]=r['state']['answer']==r['truth']
    fam=collections.defaultdict(list)
    for key,p in pairs.items():
        assert set(p)=={0,1}
        fam[key[:6]].append(p[0] and p[1])
    groups=collections.defaultdict(list)
    for key,vals in fam.items():groups[key[1:]].append({'family':key[0],'rate':sum(vals)/len(vals),'pairs':len(vals)})
    result=[];rng=np.random.default_rng(181819)
    inds=np.concatenate([rng.integers(k*16,(k+1)*16,size=(2000,16)) for k in range(3)],axis=1)
    for key,x in groups.items():
        x=sorted(x,key=lambda r:r['family']);assert len(x)==48
        vals=np.array([r['rate'] for r in x]);ci=np.quantile(vals[inds].mean(1),[.025,.975]).tolist()
        result.append(dict(zip(['depth','visibility','proxy','method','budget'],key),families=48,pairs=sum(r['pairs'] for r in x),both_correct_and_flip=float(vals.mean()),family_bootstrap_95=ci))
    save(OUT/'cpu-counterfactual-summary.json',result)
    print(json.dumps({'test_counterfactual_pairs':len(pairs),'groups':len(result),'complete':True}))


if __name__=='__main__':main()
