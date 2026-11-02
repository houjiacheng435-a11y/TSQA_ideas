"""Independent edge checks and explicit same-representation/different-answer witnesses.
Counterfactual arrays stay in memory; downloaded signals are never edited.
"""
import os
import hashlib,importlib.util,json,pathlib
import numpy as np
from core import *
ROOT=pathlib.Path(__file__).resolve().parents[2];OUT=pathlib.Path(os.environ.get('V020_OUT',str(ROOT/'results/v020-evidence-fidelity')));DATA=ROOT/'data/v020-evidence-fidelity'
def dump(name,v):(OUT/name).write_text(json.dumps(v,indent=2)+'\n')
spec=importlib.util.spec_from_file_location('tt','/root/autodl-tmp/cf-run/vendor/v020/tt-sax/ttsax.py');tt=importlib.util.module_from_spec(spec);spec.loader.exec_module(tt)
# Independent small exact truth, including boundary-spanning runs and repeated maxima.
rng=np.random.default_rng(617);arrays=[np.zeros((128,2),np.float32),np.ones((128,2),np.float32),rng.choice([-.5,.49,.5,.75,1.],(128,2)).astype(np.float32)]
a=np.zeros((128,2),np.float32);a[7:18,0]=.5;a[16:20,1]=.5;a[90:95,0]=1.;arrays.append(a)
checks=0
for x in arrays:
 for width in [2,8,32]:
  tree=Tree(x,width)
  for selective in [False,True]:
   for k in KINDS:
    b=Broker(x);out=tree.query(b,k,selective);assert out==answer(x,k),(k,width,selective)
    seen=np.zeros(x.shape,bool)
    for lo,hi,c in b.calls:seen[lo:hi,c]=1
    assert b.bytes==seen.sum()*4;checks+=1
 for k in KINDS:assert EventIndex(x).query(k)[0]==answer(x,k);checks+=1
# Witness: same bytes/statistics presented to a policy, different true answer.
x=np.array(np.load(DATA/'raw/104/104.npy',mmap_mode='r')[:16384]);witness=[]
def signature(v,method,r):
 n=len(v)
 if method=='uniform':return v[::r].tobytes()
 if method=='paa':return v.reshape(-1,r,2).mean(1,dtype=np.float64).astype(np.float32).tobytes()
 if method=='minmax':return v.reshape(-1,2*r,2).min(1).tobytes()+v.reshape(-1,2*r,2).max(1).tobytes()
 if method=='sax':
  b=max(1,r//4);mu=v.mean(0,dtype=np.float64);sd=v.std(0,dtype=np.float64);means=v.reshape(-1,b,2).mean(1,dtype=np.float64);codes=np.searchsorted(norm.ppf([.2,.4,.6,.8]),(means-mu)/sd).astype(np.uint8)
  # Exact stored Gaussian normalization metadata, not just symbols.
  return codes.tobytes()+mu.tobytes()+sd.tobytes()
 if method=='ttsax':
  b=max(1,r//2);mu=v.mean(0,dtype=np.float64);sd=v.std(0,dtype=np.float64)
  return (';'.join(tt.ttsax(v[:,c],w=n//b) for c in range(2))).encode()+mu.tobytes()+sd.tobytes()
for method in ['uniform','paa','minmax','sax','ttsax']:
 for r in [4,16,64,256]:
  b=r if method in ['uniform','paa'] else 2*r if method=='minmax' else max(1,r//(4 if method=='sax' else 2));sig=signature(x,method,r);found=False
  for bi in range(min(len(x)//b,512)):
   lo=bi*b;hi=lo+b
   if method=='uniform':idx=np.arange(lo+1,hi)
   else:idx=np.arange(lo,hi)
   if len(idx)<2:continue
   if not ((x[idx,0]>=.5).any() and (x[idx,0]<.5).any()):continue
   for reverse in [False,True]:
    y=x.copy();order=np.argsort(y[idx,0],kind='stable');order=order[::-1] if reverse else order;y[idx,0]=x[idx[order],0]
    differences={k:[answer(x,k),answer(y,k)] for k in ['count','first','ordering','cooccur','argmax'] if answer(x,k)!=answer(y,k)}
    if differences and signature(y,method,r)==sig:
     witness.append({'method':method,'ratio':r,'record':'104','start':0,'n':len(x),'block':[lo,hi],'changed_channel':0,'operation':'stable descending sort' if reverse else 'stable ascending sort','exclude_first_sample_of_block':method=='uniform','same_representation_bytes':True,'signature_sha256':hashlib.sha256(sig).hexdigest(),'answer_changes':differences,'scope':'Explicit ambiguity witness for these answers, not a clinical counterfactual or a primary test record.'});found=True;break
   if found:break
  if not found:witness.append({'method':method,'ratio':r,'witness_found':False,'scope':'No certified witness found by this bounded search; no claim of identifiability or loss.'})
dump('ambiguity-witnesses.json',witness);dump('independent-checks.json',{'passed':checks,'checks':'Exact rule equivalence and raw-read accounting on four boundary/tie/adversarial arrays; no model training.','witness_count':sum(v.get('same_representation_bytes',False) for v in witness),'witness_attempts':len(witness)})
print(checks,'edge checks; witnesses',sum(v.get('same_representation_bytes',False) for v in witness))
