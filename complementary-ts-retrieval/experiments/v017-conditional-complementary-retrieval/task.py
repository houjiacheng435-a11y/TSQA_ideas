"""Controlled episode-matching diagnostic, not a natural-data benchmark.

Only index() and successfully fetched records are visible to policies. Private
candidate kinds, worlds and labels stay outside their input. Numeric verifier
uses observations, not the hidden answer. Complete 42-point traces permit a
no-pulse observation to settle the conjunction without another retrieval.
"""
import copy
import hashlib
import json
import random

SEED = 'direction3-v017-20261031'
LENGTH = 42
BUDGET = 2


def seed(s): return int(hashlib.sha256((SEED+'|'+str(s)).encode()).hexdigest()[:16],16)
def opaque(s): return hashlib.sha256((SEED+'|id|'+str(s)).encode()).hexdigest()[:10]
def dump(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f: json.dump(x,f,ensure_ascii=False,indent=2)


def signal(f, role, start):
    rng=random.Random(seed((f,role)))
    vals=[round(rng.uniform(-.09,.09),5) for _ in range(LENGTH)]
    if start is not None:
        for k,a in enumerate([2.25,5.,3.6,1.4]): vals[start+k]+=a
    return vals


def context(f):
    r=random.Random(seed(('context',f)))
    return [round(r.uniform(-2,2),5) for _ in range(8)]


def onset(e):
    # Known scale/noise contract, independent of family or reference answer.
    return next((i for i,v in enumerate(e['values']) if v>1.5),None)


def verify(public, evidence):
    chosen={}
    for e in evidence:
        if e['channel'] in public['targets'] and e['context']==public['episode_context']:
            assert len(e['values'])==LENGTH
            chosen[e['channel']]=e
    times={k:onset(e) for k,e in chosen.items()}
    # "Both pulse AND Q is exactly two samples after P" is false if either
    # complete in-episode channel has no pulse, independent of the other one.
    if any(v is None for v in times.values()):
        return {'sufficient':True,'answer':'NO','onsets':times}
    p,q=public['targets']
    if p in times and q in times:
        return {'sufficient':True,'answer':'YES' if times[q]-times[p]==2 else 'NO','onsets':times}
    return {'sufficient':False,'answer':'UNKNOWN','onsets':times}


def build_family(f):
    names=[opaque(('channel',f,k)) for k in range(4)]
    p,q,r,s=names
    c=context(f)
    near=c.copy();near[0]+=0.15;near[5]-=0.17
    wrong=context(f+1000)
    starts=[7+f%3,25+(2*f)%4]
    records=[]
    for ai,bi,visible in [(a,b,v) for a in [0,1] for b in [0,1] for v in [0,1]]+[(2,0,0),(0,2,1)]:
        pp=None if ai==2 else starts[ai]
        qq=None if bi==2 else starts[bi]+2
        true=[{'channel':p,'context':c,'values':signal(f,'P',pp)},
              {'channel':q,'context':c,'values':signal(f,'Q',qq)}]
        pool=[]
        types=['P_same','Q_same','P_wrong_episode','Q_wrong_episode','P_near_episode','Q_near_episode','irrelevant_same','irrelevant_other']
        raw=[true[0],true[1],
             {'channel':p,'context':wrong,'values':signal(f+1000,'P',12)},
             {'channel':q,'context':wrong,'values':signal(f+1000,'Q',14)},
             {'channel':p,'context':near,'values':signal(f+2000,'P',9)},
             {'channel':q,'context':near,'values':signal(f+2000,'Q',11)},
             {'channel':r,'context':c,'values':signal(f+3000,'R',7)},
             {'channel':s,'context':context(f+3000),'values':signal(f+3000,'S',13)}]
        # IDs/order depend on family and kind only, never ai/bi/answer.
        order=list(range(8));random.Random(seed(('order',f))).shuffle(order)
        for k in order:
            item=copy.deepcopy(raw[k]);item['id']=opaque(('candidate',f,k))
            pool.append(item)
        index=[{'id':e['id'],'channel':e['channel'],'clock_start':0,'clock_end':LENGTH-1,
                'context_sketch':e['context'][:4]} for e in pool]
        public={'targets':[p,q],'episode_context':c,
                'question':'Do BOTH target channels contain a positive pulse, with the SECOND target pulse starting exactly 2 sample steps after the FIRST? Pair channels only when the 8-point context observations match exactly. Each fetched item contains its complete 42-point trace. Different episodes reuse local clocks 0..41; clock labels do not identify an episode.',
                'initial':[copy.deepcopy(true[visible])],'index':index,'budget':BUDGET}
        expected='YES' if pp is not None and qq is not None and qq-pp==2 else 'NO'
        assert verify(public,true)['answer']==expected
        for rotation in range(8):
            pub=copy.deepcopy(public);pub['index']=index[rotation:]+index[:rotation]
            needed='Q_same' if visible==0 else 'P_same'
            record={'id':f'F{f:02d}-{ai}{bi}-V{visible}-R{rotation}','family':f,'ai':ai,'bi':bi,
                'visible':visible,'rotation':rotation,'public':pub,'pool':pool,'answer':expected,
                'private_kinds':{opaque(('candidate',f,k)):types[k] for k in range(8)},
                'needed_id':opaque(('candidate',f,types.index(needed))),
                'initial_sufficient':pp is None if visible==0 else qq is None}
            records.append(record)
    return records


class Broker:
    def __init__(self,episode,budget=BUDGET):
        self.public=copy.deepcopy(episode['public'])
        self.public['budget']=budget
        self._pool={e['id']:copy.deepcopy(e) for e in episode['pool']}
        self.evidence=copy.deepcopy(self.public['initial'])
        self.selected=[];self.events=[];self.budget=budget

    def index(self):
        return copy.deepcopy(self.public['index'])

    def fetch(self,candidate_id):
        if len(self.selected)>=self.budget:raise ValueError('retrieval budget exhausted')
        if candidate_id not in self._pool:raise ValueError('unknown candidate id')
        if candidate_id in self.selected:raise ValueError('duplicate fetch')
        item=copy.deepcopy(self._pool[candidate_id])
        self.selected.append(candidate_id);self.evidence.append(item)
        self.events.append({'action':'fetch','candidate_id':candidate_id,'obtained':item,'numeric_state':self.verify()})
        return copy.deepcopy(item)

    def verify(self):return verify(self.public,self.evidence)

    def result(self):
        state=self.verify()
        return {'selected':self.selected,'evidence':self.evidence,'events':self.events,
                'numeric':state,'retrievals':len(self.selected)}


def similarity(public,item):
    if item['channel'] not in public['targets']:return -100.
    return -sum((x-y)**2 for x,y in zip(public['episode_context'][:4],item['context_sketch']))


def policy(episode,method,budget=BUDGET):
    b=Broker(episode,budget)
    ranked=sorted(enumerate(b.index()),key=lambda it:(-similarity(b.public,it[1]),it[0]))
    while not b.verify()['sufficient'] and len(b.selected)<budget:
        available=[(i,e) for i,e in ranked if e['id'] not in b.selected]
        if method=='independent_topk':candidate=available[0][1]
        elif method=='coverage':
            covered={e['channel'] for e in b.evidence if e['context']==b.public['episode_context']}
            def score(e):
                fresh=e['channel'] in b.public['targets'] and e['channel'] not in covered
                return similarity(b.public,e)+(10. if fresh else 0.)
            candidate=max(available,key=lambda it:(score(it[1]),-it[0]))[1]
        elif method=='state_rule':
            missing=[ch for ch in b.public['targets'] if ch not in b.verify()['onsets']]
            choices=[(i,e) for i,e in available if e['channel'] in missing]
            candidate=max(choices,key=lambda it:(similarity(b.public,it[1]),-it[0]))[1]
        elif method=='oracle':
            candidate=next(e for _,e in available if e['id']==episode['needed_id'])
        else:raise ValueError(method)
        b.fetch(candidate['id'])
    r=b.result();r['method']=method;r['declared_sufficient']=r['numeric']['sufficient']
    r['answer']=r['numeric']['answer'];r['budget']=budget
    return r
