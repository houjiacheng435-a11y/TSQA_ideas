import os
import hashlib,importlib.util,json,pathlib,sys,time
import numpy as np,pandas as pd
from core import *
ROOT=pathlib.Path(__file__).resolve().parents[2];OUT=pathlib.Path(os.environ.get('V020_OUT',str(ROOT/'results/v020-evidence-fidelity')));DATA=ROOT/'data/v020-evidence-fidelity'
PROTO=json.load(open(pathlib.Path(__file__).with_name('protocol.json')))
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def py(v):return v.item() if isinstance(v,np.generic) else v

def main():
 spec=importlib.util.spec_from_file_location('ttsax','/root/autodl-tmp/cf-run/vendor/v020/tt-sax/ttsax.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 selection=json.load(open(OUT/'data-selection.json'));manifest=json.load(open(OUT/'acquisition.json'));rawhash={pathlib.Path(x['file']).stem:x['sha256'] for x in manifest if x['file'].endswith('.npy')}
 allrows=[];allquality=[];build=[];qa=[];contexts=[]
 for rid in selection['records']:
  mm=np.load(DATA/f'raw/{rid}/{rid}.npy',mmap_mode='r');assert mm.dtype==np.float32 and mm.ndim==2 and mm.shape[1]==2
  start=0
  for n in PROTO['lengths']:
   cid=f'{rid}-s{start}-n{n}';casepath=OUT/'contexts'/f'{cid}.json'
   if casepath.exists():
    old=json.load(open(casepath));
    for row in old['rows']:
     if row['method']=='full_resolution':row['raw_bytes']=n*4*(2 if row['kind'] in ['ordering','cooccur'] else 1)
    save(casepath,old);allrows.extend(old['rows']);allquality.extend(old['quality']);build.extend(old['build']);qa.extend(old['qa']);contexts.append(old['context']);start+=n;print('reused',cid,flush=True);continue
   x=np.array(mm[start:start+n],copy=True);assert len(x)==n and np.isfinite(x).all()
   context={'id':cid,'record':rid,'start_sample':start,'n':n,'hz':128,'channels':['ECG1','ECG2'],'dtype':'float32','raw_bytes':x.nbytes,'source_sha256':rawhash[rid],'unit':'released numeric signal units; conversion manifest does not state physical units','timestamps':'relative sample time; no invented absolute acquisition timestamp'}
   contexts.append(context);rows=[];quality=[];bs=[];qrows=[]
   for k in KINDS:
    t0=time.perf_counter();truth=answer(x,k);secs=time.perf_counter()-t0
    q={'id':cid+'-'+k,'query':k,'timeseries_reference':{'record':rid,'start_sample':start,'n':n,'sha256':rawhash[rid]},'available_channels':['ECG1','ECG2'],'ground_truth':truth,'evidence_annotation':{'source':'declared numeric threshold predicate, not human clinical labels','threshold':1. if k in ['exists10','duration'] else .5},'metadata':{'split':'official-record-test','hz':128,'context':cid}}
    qrows.append(q);rows.append({'context':cid,'record':rid,'n':n,'kind':k,'method':'full_resolution','ratio_target':1,'answer':truth,'truth':truth,'correct':True,'certified':True,'raw_bytes':len(x)*4*(2 if k in ['ordering','cooccur'] else 1),'summary_bytes_read':0,'index_bytes':0,'online_seconds':secs,'offline_seconds':0.})
   t0=time.perf_counter();events=EventIndex(x);bs.append({'context':cid,'record':rid,'n':n,'method':'event_index','ratio_target':0,'seconds':events.seconds,'index_bytes':events.storage,'input_bytes':x.nbytes,'scan_note':'Two predeclared threshold passes per channel + global max/argmax and half means; input_bytes = distinct source bytes, not total memory traffic.'})
   for q in qrows:
    t0=time.perf_counter();ans,readbytes=events.query(q['query']);elapsed=time.perf_counter()-t0
    assert ans==q['ground_truth'],(cid,q['query'],ans,q['ground_truth'])
    rows.append({'context':cid,'record':rid,'n':n,'kind':q['query'],'method':'event_index','ratio_target':0,'answer':py(ans),'truth':q['ground_truth'],'correct':True,'certified':True,'raw_bytes':0,'summary_bytes_read':readbytes,'index_bytes':events.storage,'online_seconds':elapsed,'offline_seconds':events.seconds})
   for r in PROTO['ratios']:
    tree=Tree(x,2*r);bs.append({'context':cid,'record':rid,'n':n,'method':'minmax_sum_tree','ratio_target':r,'seconds':tree.build_seconds,'index_bytes':tree.storage,'input_bytes':x.nbytes})
    for method in ['hierarchical_minmax_sum','query_aware_rule']:
     for q in qrows:
      broker=Broker(x);t0=time.perf_counter();ans=tree.query(broker,q['query'],selective=method=='query_aware_rule');elapsed=time.perf_counter()-t0
      assert ans==q['ground_truth'],(cid,method,q['query'],ans,q['ground_truth'])
      row={'context':cid,'record':rid,'n':n,'kind':q['query'],'method':method,'ratio_target':r,'answer':py(ans),'truth':q['ground_truth'],'correct':True,'certified':True,'raw_bytes':broker.bytes,'summary_bytes_read':tree.reads,'index_bytes':tree.storage,'online_seconds':elapsed,'offline_seconds':tree.build_seconds,'raw_fetch_calls':len(broker.calls)};rows.append(row)
      trace=OUT/'refinement-traces'/f'{cid}-r{r}-{method}-{q["query"]}.json';save(trace,{'query_id':q['id'],'method':method,'leaf':2*r,'reads':broker.calls,'answer':py(ans),'raw_bytes':broker.bytes,'summary_bytes_read':tree.reads,'access_rule':'Only counted Broker.fetch sees original values. Index built once offline without labels.'})
    for method in ['uniform','paa','minmax','pla_bound','sax','ttsax_level_diagnostic']:
     decoded,meta,size,seconds=compress(x,r,method,m.ttsax)
     bs.append({'context':cid,'record':rid,'n':n,'method':method,'ratio_target':r,'seconds':seconds,'index_bytes':size,'input_bytes':x.nbytes,'actual_ratio':x.nbytes/size})
     met=evidence(decoded[:,0]>=.5,x[:,0]>=.5);quality.append({'context':cid,'record':rid,'n':n,'method':method,'ratio_target':r,'actual_ratio':x.nbytes/size,**met,'scope':'Signal reconstruction event matching, not a proof of intrinsic information loss. TT-SAX row uses level-word reconstruction only; not a full TT-SAX answering system.'})
     for q in qrows:
      t0=time.perf_counter();ans,cert=fixed_answer(decoded,meta,method,q['query']);elapsed=time.perf_counter()-t0
      rows.append({'context':cid,'record':rid,'n':n,'kind':q['query'],'method':method,'ratio_target':r,'answer':py(ans),'truth':q['ground_truth'],'correct':ans==q['ground_truth'],'certified':cert,'raw_bytes':0,'summary_bytes_read':size,'index_bytes':size,'online_seconds':elapsed,'offline_seconds':seconds,'note':'Decoder diagnostic only, no LLM; UNKNOWN is a valid abstention and not answer preservation. TT-SAX full trend word is not used by this diagnostic decoder.'})
   pack={'context':context,'rows':rows,'quality':quality,'build':bs,'qa':qrows};save(casepath,pack);allrows.extend(rows);allquality.extend(quality);build.extend(bs);qa.extend(qrows);start+=n
   print(json.dumps({'context':cid,'questions':len(qrows),'rows':len(rows),'min':float(x.min()),'max':float(x.max())}),flush=True)
 save(OUT/'qa.json',qa);save(OUT/'contexts.json',contexts)
 pd.DataFrame(allrows).to_csv(OUT/'raw-results.csv',index=False);pd.DataFrame(allquality).to_csv(OUT/'evidence-metrics.csv',index=False);pd.DataFrame(build).to_csv(OUT/'index-build.csv',index=False)
 save(OUT/'cpu-complete.json',{'complete':True,'queries':len(qa),'contexts':len(contexts),'records':len(selection['records']),'rows':len(allrows),'protocol_sha256':hashlib.sha256(pathlib.Path(__file__).with_name('protocol.json').read_bytes()).hexdigest()})
 print('CPU COMPLETE',len(qa),len(allrows),flush=True)
if __name__=='__main__':main()
