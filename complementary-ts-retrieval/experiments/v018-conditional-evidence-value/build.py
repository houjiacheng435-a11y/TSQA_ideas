"""Freeze family-separated data and prove necessities before any GPU inference."""
import copy
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import numpy as np
from core import *

HERE=Path(__file__).parent;OUT=HERE.parents[1]/'results/v018-conditional-evidence-value'


def main():
    assert not (OUT/'audit.complete.json').exists(),'Never overwrite completed outputs'
    OUT.mkdir(parents=True,exist_ok=True)
    protocol=json.loads((HERE/'protocol.json').read_text())
    if (OUT/'protocol.json').exists():assert json.loads((OUT/'protocol.json').read_text())==protocol
    else:save(OUT/'protocol.json',protocol)
    families=[make_family(s,split,i) for s in protocol['seeds'] for split,n in protocol['families_per_seed'].items() for i in range(n)]
    if (OUT/'families-private.json').exists():assert json.loads((OUT/'families-private.json').read_text())==families
    else:save(OUT/'families-private.json',families)
    episodes=[];audit=[]
    for f in families:
        assert np.allclose(sorted(f['profiles'][0]),sorted(f['profiles'][1]),atol=1e-6)
        for d in [0,1,2]:
            for ys in itertools.product([0,1],repeat=2):
                for s in [0,1]:
                    for vis,ms in [('clear',[0]),('blind',[0,1])]:
                        for mapping in ms:
                            for proxy in [False,True]:episodes.append(make_episode(f,d,ys,s,vis,mapping,proxy))
            # Certificates are checked for every independent family and regime;
            # every possible finite latent state is covered separately below.
            e0=make_episode(f,d,(0,1),0);e1=make_episode(f,d,(0,1),1)
            b0=Broker(f,e0,4);b1=Broker(f,e1,4)
            assert b0.records==b1.records,'Changing only initial evidence must preserve the entire pool'
            optimal=[]
            for b in [b0,b1]:
                vals={x['id']:public_value(b,x,d+1) for x in b.index}
                best=max(vals.values());opt={k for k,v in vals.items() if abs(v-best)<1e-8}
                assert abs(best-1.)<1e-8
                assert opt and all(b.records[k]['bundle_number']==b.known_group for k in opt)
                optimal.append(opt)
                target=b.known_group
                for size in range(d+1):
                    for subset in itertools.combinations(required(d),size):
                        t=Broker(f,b.e,4)
                        for kind in subset+('proxy',):
                            cid=next(x['id'] for x in t.index if x['bundle_number']==target and x['kind']==kind)
                            t.fetch(cid)
                        assert not t.state()['sufficient'],('unexpected shortcut',f['id'],d,subset)
                t=Broker(f,b.e,3)
                for kind in required(d):
                    t.fetch(next(x['id'] for x in t.index if x['bundle_number']==target and x['kind']==kind))
                assert t.state()['sufficient'] and t.state()['answer']==('YES' if b.e['ys'][b.e['source']]==0 else 'NO')
            assert not(optimal[0]&optimal[1]),'Optimal sets must flip with the source waveform'
            blind0=Broker(f,make_episode(f,d,(0,1),0,'blind',0));blind1=Broker(f,make_episode(f,d,(0,1),0,'blind',1))
            assert blind0.public()==blind1.public(),'Hidden routing swaps must be publicly indistinguishable'
            # A label flip preserves every public preview and all scalar target statistics.
            yflip=Broker(f,make_episode(f,d,(1,0),0),4)
            assert b0.public()==yflip.public()
            for cid,x in b0.records.items():assert sorted(x['values'])==sorted(yflip.records[cid]['values'])
            audit.append({'family':f['id'],'depth':d,'same_pool_initial_change':True,'optimal_sets_disjoint':True,
                'blind_mapping_indistinguishable':True,'public_initial_and_previews_equal_after_label_flip':True,
                'source_and_candidate_scalar_histograms_matched':True,
                'proper_subsets_even_with_proxy_insufficient':True,'required_set_sufficient':True})
        print(json.dumps({'family_audited':f['id']}),flush=True)
    # Exhaustive finite-state necessity: all possible unknown clock offsets,
    # both answers, and all proxy phase observations have nonzero prior support.
    exhaustive=0
    for d in [0,1,2]:
        y,vals=worlds(d)
        for w in range(len(y)):
            full={k:int(v[w]) for k,v in vals.items()}
            for size in range(d+1):
                for subset in itertools.combinations(required(d),size):
                    for proxy_phase in range(M):
                        obs={k:full[k] for k in subset};obs['proxy']=proxy_phase
                        p=posterior(d,tuple(sorted(obs.items())))
                        py=np.bincount(y,weights=p,minlength=2)
                        assert np.all(py>0)
                        exhaustive+=1
            p=posterior(d,tuple(sorted(full.items())))
            assert np.count_nonzero(np.bincount(y,weights=p,minlength=2)>1e-12)==1
    with gzip.open(OUT/'episodes-private.jsonl.gz','wt') as f:
        for e in episodes:f.write(json.dumps(e)+'\n')
    # All held-out families, fixed balanced CF worlds; no post-score substitutions.
    gpu=[];reader=[]
    for f in families:
        if f['split']!='test':continue
        for d in [0,1,2]:
            for ys in [(0,0),(1,1)]:
                for s in [0,1]:
                    gpu.append(make_episode(f,d,ys,s,'clear',0,True))
                    if d>0:gpu.append(make_episode(f,d,ys,s,'blind',0,True))
                reader.append(make_episode(f,d,ys,f['index']%2,'clear',0,True))
    assert len(gpu)==960 and len(reader)==288
    save(OUT/'gpu-episodes-private.json',gpu);save(OUT/'reader-episodes-private.json',reader)
    save(OUT/'audit.json',{'complete':True,'families':len(families),'test_families':48,'episodes':len(episodes),
        'family_regime_certificates':audit,'exhaustive_partial_world_checks':exhaustive,
        'no_performance_filter':True,'mmr_grid_predefined':[.25,.5,.75,1.],
        'public_blind_bound':'B3, budget 3: first bundle is equiprobable; a wrong first fetch leaves fewer than three needed records. Public success at most 1/2; hidden-result oracle can reach 1.',
        'theory_note':'Phase/clock uncertainty induces known higher-order information complementarity; this is not a novelty claim.'})
    save(OUT/'audit.complete.json',{'complete':True,'gpu_gate_passed':True,'episodes':len(episodes),'gpu_episodes':len(gpu),'reader_episodes':len(reader),
        'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [HERE/'core.py',HERE/'build.py',HERE/'protocol.json']}})
    print(json.dumps({'complete':True,'families':len(families),'episodes':len(episodes),'exhaustive_checks':exhaustive}),flush=True)


if __name__=='__main__':main()
