"""Numeric evidence interface. Policies see only public indexes + counted raw broker.
Intervals are half-open sample coordinates. No clinical meaning is assigned.
"""
import time
import numpy as np
from scipy.stats import norm

KINDS=['exists05','exists10','count','first','argmax','maximum','trend','ordering','cooccur','duration']
def runs(mask):
    d=np.diff(np.r_[False,mask,False].astype(np.int8));return np.column_stack((np.flatnonzero(d==1),np.flatnonzero(d==-1))).astype(np.int32)
def first(mask):
    a=np.flatnonzero(mask);return int(a[0]) if len(a) else None
def answer(x,kind):
    a=x[:,0]>=.5
    if kind=='exists05':return bool(a.any())
    if kind=='exists10':return bool((x[:,0]>=1).any())
    if kind=='count':return int(len(runs(a)))
    if kind=='first':return first(a)
    if kind=='argmax':return int(np.argmax(x[:,0]))
    if kind=='maximum':return round(float(x[:,0].max()),3)
    if kind=='trend':return bool(np.mean(x[len(x)//2:,0],dtype=np.float64)>np.mean(x[:len(x)//2,0],dtype=np.float64))
    if kind=='ordering':
        aa,bb=first(a),first(x[:,1]>=.5)
        return 'NONE' if aa is None or bb is None else ('A' if aa<bb else 'B' if bb<aa else 'TIE')
    if kind=='cooccur':return bool((a & (x[:,1]>=.5)).any())
    if kind=='duration':return int((x[:,0]>=1).sum())
    raise KeyError(kind)

def evidence(pred,gt,hz=128):
    pp=runs(pred);gg=runs(gt)
    if not len(gg):return {'gt_events':0,'event_recall50':None,'mean_best_iou':None,'mean_nearest_onset_error_s':None}
    if not len(pp):return {'gt_events':len(gg),'event_recall50':0.,'mean_best_iou':0.,'mean_nearest_onset_error_s':None}
    # Best IoU to any overlapping predicted interval; recall is per gold event,
    # not one-to-one detection F1. Long merged intervals get low IoU.
    vals=[];err=[]
    for a,b in gg:
        lo=np.searchsorted(pp[:,1],a,side='right');hi=np.searchsorted(pp[:,0],b,side='left');c=pp[lo:hi]
        if len(c):
            inter=np.maximum(0,np.minimum(c[:,1],b)-np.maximum(c[:,0],a));union=(b-a)+(c[:,1]-c[:,0])-inter;best=float(np.max(inter/union))
        else:best=0.
        vals.append(best)
        j=int(np.searchsorted(pp[:,0],a));err.append(min(abs(int(pp[k,0])-int(a)) for k in [max(0,j-1),min(len(pp)-1,j)])/hz)
    return {'gt_events':len(gg),'event_recall50':float(np.mean(np.array(vals)>=.5)),'mean_best_iou':float(np.mean(vals)),'mean_nearest_onset_error_s':float(np.mean(err))}

class Broker:
    def __init__(self,x):self.__x=x;self.seen=np.zeros(x.shape,dtype=bool);self.calls=[]
    def fetch(self,a,b,ch):
        assert 0<=a<b<=len(self.__x) and ch in [0,1]
        self.seen[a:b,ch]=True;self.calls.append([a,b,ch]);return np.array(self.__x[a:b,ch],copy=True)
    @property
    def bytes(self):return int(np.count_nonzero(self.seen))*4

class Tree:
    def __init__(self,x,leaf):
        start=time.perf_counter();self.n=len(x);self.leaf=leaf;v=x.reshape(-1,leaf,2)
        self.mi=[v.min(1)];self.ma=[v.max(1)];self.su=[v.sum(1,dtype=np.float64)]
        while len(self.mi[-1])>1:
            self.mi.append(self.mi[-1].reshape(-1,2,2).min(1));self.ma.append(self.ma[-1].reshape(-1,2,2).max(1));self.su.append(self.su[-1].reshape(-1,2,2).sum(1))
        self.build_seconds=time.perf_counter()-start;self.storage=sum(a.nbytes for group in [self.mi,self.ma,self.su] for a in group);self.level=len(self.mi)-1;self.reads=0
    def bounds(self,l,i,c):self.reads+=8;return float(self.mi[l][i,c]),float(self.ma[l][i,c])
    def extent(self,l,i):a=i*self.leaf*2**l;return a,a+self.leaf*2**l
    def first_above(self,broker,c,threshold,l=None,i=0):
        l=self.level if l is None else l;lo,hi=self.bounds(l,i,c);a,b=self.extent(l,i)
        if hi<threshold:return None
        if lo>=threshold:return a
        if l==0:
            f=first(broker.fetch(a,b,c)>=threshold);return None if f is None else a+f
        f=self.first_above(broker,c,threshold,l-1,i*2)
        return f if f is not None else self.first_above(broker,c,threshold,l-1,i*2+1)
    def summary(self,broker,c,threshold,l=None,i=0):
        l=self.level if l is None else l;lo,hi=self.bounds(l,i,c);a,b=self.extent(l,i)
        if hi<threshold:return (False,False,0,0,None)
        if lo>=threshold:return (True,True,1,b-a,a)
        if l==0:
            m=broker.fetch(a,b,c)>=threshold;f=first(m);return bool(m[0]),bool(m[-1]),len(runs(m)),int(m.sum()),None if f is None else a+f
        left=self.summary(broker,c,threshold,l-1,i*2);right=self.summary(broker,c,threshold,l-1,i*2+1)
        return left[0],right[1],left[2]+right[2]-int(left[1] and right[0]),left[3]+right[3],left[4] if left[4] is not None else right[4]
    def simultaneous(self,broker,l=None,i=0):
        l=self.level if l is None else l;lo0,hi0=self.bounds(l,i,0);lo1,hi1=self.bounds(l,i,1);a,b=self.extent(l,i)
        if hi0<.5 or hi1<.5:return False
        if lo0>=.5 and lo1>=.5:return True
        if l==0:return bool(((broker.fetch(a,b,0)>=.5)&(broker.fetch(a,b,1)>=.5)).any())
        return self.simultaneous(broker,l-1,i*2) or self.simultaneous(broker,l-1,i*2+1)
    def query(self,broker,kind,selective=True):
        self.reads=0
        def f(c,t):return self.first_above(broker,c,t) if selective else self.summary(broker,c,t)[4]
        if kind.startswith('exists'):
            if selective:self.reads+=4;return bool(self.ma[-1][0,0]>=(1 if kind=='exists10' else .5))
            return self.summary(broker,0,1 if kind=='exists10' else .5)[4] is not None
        if kind=='count':return int(self.summary(broker,0,.5)[2])
        if kind=='duration':return int(self.summary(broker,0,1)[3])
        if kind=='first':return f(0,.5)
        if kind=='argmax':self.reads+=4;return f(0,float(self.ma[-1][0,0]))
        if kind=='maximum':self.reads+=4;return round(float(self.ma[-1][0,0]),3)
        if kind=='trend':
            self.reads+=16;return bool(self.su[-2][1,0]>self.su[-2][0,0])
        if kind=='ordering':
            a,b=f(0,.5),f(1,.5);return 'NONE' if a is None or b is None else ('A' if a<b else 'B' if b<a else 'TIE')
        if kind=='cooccur':return self.simultaneous(broker)

class EventIndex:
    def __init__(self,x):
        start=time.perf_counter();self.events={(c,t):runs(x[:,c]>=t) for c in [0,1] for t in [.5,1.]};self.n=len(x)
        self.maximum=float(x[:,0].max());self.argmax=int(np.argmax(x[:,0]));self.trend=bool(x[self.n//2:,0].mean(dtype=np.float64)>x[:self.n//2,0].mean(dtype=np.float64));self.storage=sum(v.nbytes for v in self.events.values())+24;self.seconds=time.perf_counter()-start
    def query(self,k):
        a=self.events[0,.5];b=self.events[1,.5];cost=8
        if k=='exists05':out=bool(len(a))
        elif k=='exists10':out=bool(len(self.events[0,1.]))
        elif k=='count':out=len(a)
        elif k=='first':out=int(a[0,0]) if len(a) else None
        elif k=='argmax':out=self.argmax
        elif k=='maximum':out=round(self.maximum,3)
        elif k=='trend':out=self.trend
        elif k=='ordering':out='NONE' if not len(a) or not len(b) else ('A' if a[0,0]<b[0,0] else 'B' if b[0,0]<a[0,0] else 'TIE');cost=16
        elif k=='duration':aa=self.events[0,1.];out=int((aa[:,1]-aa[:,0]).sum());cost=aa.nbytes
        elif k=='cooccur':
            i=j=0;out=False;cost=0
            while i<len(a) and j<len(b):
                cost+=16
                if max(a[i,0],b[j,0])<min(a[i,1],b[j,1]):out=True;break
                if a[i,1]<=b[j,1]:i+=1
                else:j+=1
        return out,cost

def compress(x,r,method,ttsax=None):
    n,c=x.shape;start=time.perf_counter();meta={};bytes_=0;cert={}
    if method in ['uniform','paa']:
        v=x[::r].copy() if method=='uniform' else x.reshape(-1,r,c).mean(1,dtype=np.float64).astype(np.float32);bytes_=v.nbytes;decoded=np.repeat(v,r,axis=0)[:n]
    elif method=='minmax':
        b=2*r;vv=x.reshape(-1,b,c);mi,ma=vv.min(1),vv.max(1);bytes_=mi.nbytes+ma.nbytes;decoded=np.repeat((mi.astype(float)+ma)/2,b,axis=0)
        meta={'min':mi,'max':ma,'block':b}
    elif method=='pla_bound':
        # Fixed-partition piecewise linear interpolant plus measured sup error.
        # Use a power-of-two block >=3r, so actual byte budget is conservative.
        b=4*r;vv=x.reshape(-1,b,c);a=vv[:,0,:];z=vv[:,-1,:];line=a[:,None,:]+(z-a)[:,None,:]*np.linspace(0,1,b)[None,:,None];error=np.max(np.abs(vv-line),axis=1);error=np.nextafter(error.astype(np.float32),np.float32(np.inf));bytes_=a.nbytes+z.nbytes+error.nbytes;decoded=line.reshape(n,c);meta={'lo':(line-error[:,None,:]).reshape(n,c),'hi':(line+error[:,None,:]).reshape(n,c)}
    elif method in ['sax','ttsax_level_diagnostic']:
        b=max(1,r//(4 if method=='sax' else 2));w=n//b;mu=x.mean(0,dtype=np.float64);sd=x.std(0,dtype=np.float64);sd=np.maximum(sd,1e-12);word=[];dec=[]
        for j in range(c):
            if method=='sax':
                means=x[:,j].reshape(-1,b).mean(1);codes=np.searchsorted(norm.ppf([.2,.4,.6,.8]),(means-mu[j])/sd[j]).astype(np.uint8);word.append(codes.tobytes())
            else:
                s=ttsax(x[:,j],w=w);word.append(s.encode());codes=np.fromiter((ord(z)-97 for z in s.split('|')[1]),dtype=np.int8)
            value=norm.ppf((codes.astype(float)+.5)/5)*sd[j]+mu[j];dec.append(np.repeat(value,b))
        decoded=np.column_stack(dec);bytes_=sum(len(z) for z in word)+mu.nbytes+sd.nbytes;meta={'block':b,'normalization_mean':mu.tolist(),'normalization_std':sd.tolist()}
    else:raise KeyError(method)
    return decoded,meta,bytes_,time.perf_counter()-start

def fixed_answer(decoded,meta,method,kind):
    if method!='minmax':return answer(decoded,kind),False
    mi,ma,b=meta['min'],meta['max'],meta['block']
    if kind in ['exists05','exists10']:return bool((ma[:,0]>=(1 if kind=='exists10' else .5)).any()),True
    if kind=='maximum':return round(float(ma[:,0].max()),3),True
    if kind in ['count','duration','first','ordering','cooccur']:
        # Bounds fully determine a threshold mask only when each block is pure.
        t=1. if kind=='duration' else .5;channels=[0,1] if kind in ['ordering','cooccur'] else [0]
        if any(((mi[:,c]<t)&(ma[:,c]>=t)).any() for c in channels):return 'UNKNOWN',False
        mask=np.repeat((mi>=t).astype(float),b,axis=0)*2
        return answer(mask,kind),True
    return 'UNKNOWN',False
