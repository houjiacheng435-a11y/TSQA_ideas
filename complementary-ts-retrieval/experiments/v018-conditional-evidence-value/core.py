"""Periodic sensor-response/clock-calibration task and exact public belief model.

Units: 8 phase bins, 48 raw samples/cycle. A response's local phase equals
source phase + true delay + unknown clock offsets (mod 8). Calibration links
measure the offsets. The coarse proxy has full-support independent phase noise.
None of the ranking/verification functions reads an episode's true delay.
"""
import copy
import hashlib
import itertools
import json
import math
import random
from functools import lru_cache
import numpy as np

M=8;N=48;KINDS=('response','clock1','clock2','proxy')
ROOT_SEED='direction3-v018-20261031'


def hashed(*args):return int(hashlib.sha256((ROOT_SEED+repr(args)).encode()).hexdigest()[:16],16)
def oid(*args):return hashlib.sha256((ROOT_SEED+'id'+repr(args)).encode()).hexdigest()[:10]
def save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False)
def normalize(a):
    a=np.asarray(a,dtype=float);return (a-a.mean())/max(float(a.std()),1e-12)
def waveform(phase):
    return np.roll(np.cos(2*np.pi*np.arange(N)/N),int(phase)*(N//M)).round(7).tolist()
def phase(values):
    assert len(values)==N
    i=int(np.argmax(values));assert i%(N//M)==0
    return i//(N//M)
@lru_cache(32768)
def _ncc(a,b):
    a=normalize(a);b=normalize(b)
    return float(max(np.dot(a,np.roll(b,k))/len(a) for k in range(len(a))))
def ncc(a,b):return _ncc(tuple(a),tuple(b))
def required(depth):return ('response',)+tuple('clock'+str(i+1) for i in range(depth))
def entropy(p):
    p=np.asarray(p);p=p[p>1e-14];return float(-np.sum(p*np.log2(p)))


def make_family(seed,split,index):
    uid=f'{seed}-{split}-{index:02d}';rng=random.Random(hashed(uid))
    freqs={'train':(1,5),'development':(1,7),'test':(5,7)}[split]
    aa,bb=rng.uniform(.05,.2),rng.uniform(.01,.08)
    profiles=[];phis=[]
    for f in freqs:
        x=np.cos(2*np.pi*f*np.arange(N)/N)+aa*np.cos(4*np.pi*f*np.arange(N)/N)+bb*np.cos(6*np.pi*f*np.arange(N)/N)
        p=rng.randrange(M);phis.append(p)
        profiles.append(np.roll(normalize(x),p*(N//M)).round(7).tolist())
    offsets=[[rng.randrange(M),rng.randrange(M)] for _ in range(2)]
    noise=[]
    for _ in range(2):noise.append(0 if rng.random()<.5 else rng.randrange(1,M))
    order=list(range(8));rng.shuffle(order)
    return {'id':uid,'seed':seed,'split':split,'index':index,'profiles':profiles,
            'phis':phis,'offsets':offsets,'noise':noise,'order':order,'base_map':rng.randrange(2)}


def pool(f,depth,ys,mapping):
    items=[]
    for bundle in [0,1]:
        physical=bundle^mapping^f['base_map']
        u=f['offsets'][physical]
        lag=2+4*ys[physical]
        phases={'response':(f['phis'][physical]+lag+sum(u[:depth]))%M,
                'clock1':u[0],'clock2':u[1],'proxy':(lag+f['noise'][physical])%M}
        for kind in KINDS:
            items.append({'id':oid(f['id'],bundle,kind),'bundle':oid(f['id'],'bundle',bundle),
                'bundle_number':bundle,'kind':kind,'clock_start':0,'clock_end':N-1,
                'driver':f['profiles'][physical], 'values':waveform(phases[kind])})
    return [items[k] for k in f['order']]


QUESTION='Does the downstream response associated with this driving waveform have true delay 2 rather than 6 phase bins? One cycle has 8 bins and 48 raw samples. Use only acquired records. Local response phase = source phase + delay + the required clock offsets, modulo 8. Each clock record measures its offset. The coarse proxy has full-support phase noise and cannot certify the answer alone.'


def make_episode(f,depth,ys,source,visibility='clear',mapping=0,proxy=True):
    eid=f"{f['id']}-d{depth}-y{ys[0]}{ys[1]}-s{source}-{visibility}-m{mapping}-p{int(proxy)}"
    return {'id':eid,'family':f['id'],'depth':depth,'ys':list(ys),'source':source,
            'visibility':visibility,'mapping':mapping,'proxy':proxy}


class Broker:
    def __init__(self,f,e,budget=3):
        self.f=f;self.e=e;self.depth=e['depth'];self.budget=budget
        self.records={x['id']:x for x in pool(f,e['depth'],e['ys'],e['mapping']) if e['proxy'] or x['kind']!='proxy'}
        self.source=f['profiles'][e['source']]
        self.index=[]
        for x in self.records.values():
            self.index.append({k:x[k] for k in ['id','bundle','bundle_number','kind','clock_start','clock_end']})
            self.index[-1]['driver_sketch']=x['driver'][::3] if e['visibility']=='clear' else None
        self.known_group=self._public_match() if e['visibility']=='clear' else None
        self.observations={};self.selected=[];self.events=[]

    def _public_match(self):
        scores={x['bundle_number']:ncc(self.source[::3],x['driver_sketch']) for x in self.index}
        assert sorted(scores.values())[-1]-sorted(scores.values())[0]>.2
        return max(scores,key=scores.get)

    def public(self,raw=False):
        data={'question':QUESTION,'clock_depth':self.depth,'required_clock_links':list(required(self.depth)[1:]),
              'initial_source':self.source if raw else {'source_phase':phase(self.source)},
              'budget_remaining':self.budget-len(self.selected),'candidate_index':copy.deepcopy(self.index),
              'obtained':self.events}
        if not raw:
            for row in data['candidate_index']:
                row['context_ncc']=ncc(self.source[::3],row['driver_sketch']) if row['driver_sketch'] else None
                row.pop('driver_sketch')
            data['obtained']=[{k:x[k] for k in ['id','bundle_number','kind','observed_phase','matches_source']} for x in self.events]
        return data

    def fetch(self,cid):
        if cid not in self.records:raise ValueError('unknown candidate')
        if cid in self.selected:raise ValueError('duplicate fetch')
        if len(self.selected)>=self.budget:raise ValueError('budget exhausted')
        x=copy.deepcopy(self.records[cid]);bundle=x['bundle_number']
        match=ncc(self.source,x['driver'])>.99
        group=bundle if match else 1-bundle
        if self.known_group is not None:assert group==self.known_group
        self.known_group=group
        value=phase(x['values'])
        if match:
            self.observations[x['kind']]=(value-phase(self.source))%M if x['kind']=='response' else value
        self.selected.append(cid)
        event={**x,'observed_phase':value,'matches_source':match}
        self.events.append(event)
        return event

    def state(self):
        p=posterior(self.depth,tuple(sorted(self.observations.items())))
        yp=np.bincount(worlds(self.depth)[0],weights=p,minlength=2)
        support=[i for i,v in enumerate(yp) if v>1e-12]
        return {'sufficient':len(support)==1,'answer':('YES' if support[0]==0 else 'NO') if len(support)==1 else 'UNKNOWN',
                'posterior_yes':float(yp[0]),'known_group':self.known_group,
                'observations':dict(self.observations)}


@lru_cache(None)
def worlds(depth):
    rows=list(itertools.product(range(2),*([range(M)]*depth)))
    y=np.array([x[0] for x in rows]);u=np.array([x[1:] for x in rows],dtype=int).reshape(len(rows),depth)
    values={'response':(2+4*y+u.sum(axis=1))%M}
    for j in range(depth):values['clock'+str(j+1)]=u[:,j]
    return y,values


@lru_cache(None)
def posterior(depth,observed):
    y,vals=worlds(depth);p=np.ones(len(y),dtype=float)/len(y)
    for kind,value in observed:
        if kind=='proxy':p*=np.where((2+4*y)%M==value,.5,.5/7)
        elif kind in vals:p*=vals[kind]==value
    assert p.sum()>0,'No compatible physical world'
    return p/p.sum()


def h(depth,obs,joint=False):
    p=posterior(depth,obs)
    return entropy(p) if joint else entropy(np.bincount(worlds(depth)[0],weights=p,minlength=2))


@lru_cache(None)
def outcomes(depth,obs,kind):
    y,vals=worlds(depth);p=posterior(depth,obs);ans=[]
    for value in range(M):
        if kind=='proxy':prob=float(np.sum(p*np.where((2+4*y)%M==value,.5,.5/7)))
        elif kind in vals:prob=float(np.sum(p[vals[kind]==value]))
        else:prob=1./M
        if prob>1e-12:
            new=dict(obs);new[kind]=value;ans.append((prob,tuple(sorted(new.items()))))
    return tuple(ans)


@lru_cache(None)
def future_h(depth,obs,steps,proxy=True):
    now=h(depth,obs)
    if steps==0 or now<1e-12:return now
    actions=[k for k in required(depth)+(('proxy',) if proxy else ()) if k not in dict(obs)]
    if not actions:return now
    return min(sum(p*future_h(depth,o,steps-1,proxy) for p,o in outcomes(depth,obs,k)) for k in actions)


def public_value(b,item,steps=1,joint=False):
    kind=item['kind'];depth=b.depth;obs=tuple(sorted(b.observations.items()))
    if b.known_group is not None and item['bundle_number']!=b.known_group:return 0.
    if kind not in required(depth) and kind!='proxy':return 0.
    base=h(depth,obs,joint)
    def after(o):return h(depth,o,True) if joint else future_h(depth,o,steps-1,b.e['proxy'])
    matched=sum(p*after(o) for p,o in outcomes(depth,obs,kind))
    if b.known_group is None:
        # Any fetched driver reveals association; a wrong-bundle value gives
        # no information about target delay/offsets. No hidden mapping is used.
        unmatched=h(depth,obs,True) if joint else future_h(depth,obs,steps-1,b.e['proxy'])
        return base+1.-.5*(matched+unmatched) if joint else base-.5*(matched+unmatched)
    return base-matched


def priority(b,item):
    # Strong transparent tie-breaker follows the public calibration dependency,
    # never a hidden true phase or outcome.
    return (item['kind'] in required(b.depth),item['kind']=='response',-KINDS.index(item['kind']))


def choose(b,method,mmr_lambda=.75):
    available=[x for x in b.index if x['id'] not in b.selected]
    pos={x['id']:i for i,x in enumerate(b.index)}
    def corr(x):return ncc(b.source[::3],x['driver_sketch']) if x['driver_sketch'] is not None else 0.
    def association(x):return 1. if b.known_group==x['bundle_number'] else (0. if b.known_group is None else -1.)
    if method=='clairvoyant_oracle':
        target=b.e['source']^b.e['mapping']^b.f['base_map']
        return max(available,key=lambda x:(x['bundle_number']==target,x['kind'] in required(b.depth),priority(b,x),-pos[x['id']]))
    if method=='content_topk':return max(available,key=lambda x:(corr(x),-pos[x['id']]))
    if method=='dependency_topk':return max(available,key=lambda x:(corr(x),priority(b,x),-pos[x['id']]))
    if method=='time_only':return available[0]
    if method=='coverage':
        covered={(x['bundle_number'],x['kind']) for x in b.events}
        return max(available,key=lambda x:(association(x) if b.known_group is not None else corr(x),
            (x['bundle_number'],x['kind']) not in covered,priority(b,x),-pos[x['id']]))
    if method=='conditional_numeric':
        return max(available,key=lambda x:(association(x),priority(b,x),-pos[x['id']]))
    if method=='mmr':
        def mmr(x):
            duplicate=max((1. if x['bundle_number']==t['bundle_number'] else 0. for t in b.events),default=0.)
            return mmr_lambda*corr(x)-(1-mmr_lambda)*duplicate
        return max(available,key=lambda x:(mmr(x),-pos[x['id']]))
    if method in ['answer_ig','answer_ig_dependency_tie','joint_state_ig','lookahead2','lookahead3']:
        steps=min(b.budget-len(b.selected),{'lookahead2':2,'lookahead3':3}.get(method,1))
        joint=method=='joint_state_ig'
        def val(x):return round(public_value(b,x,steps,joint),10)
        if method=='answer_ig':return max(available,key=lambda x:(val(x),-pos[x['id']]))
        return max(available,key=lambda x:(val(x),association(x),priority(b,x),-pos[x['id']]))
    raise ValueError(method)


def simulate(f,e,method,budget,mmr_lambda=.75):
    b=Broker(f,e,budget);checks=[b.state()]
    while not b.state()['sufficient'] and len(b.selected)<budget:
        b.fetch(choose(b,method,mmr_lambda)['id']);checks.append(b.state())
    state=b.state()
    return {'episode_id':e['id'],'family':e['family'],'method':method,'budget':budget,
            'selected':b.selected,'actions':[{'id':x['id'],'bundle_number':x['bundle_number'],'kind':x['kind'],
                'phase':x['observed_phase'],'matches_source':x['matches_source']} for x in b.events],
            'checks':checks,'state':state,'cost':len(b.selected)}
