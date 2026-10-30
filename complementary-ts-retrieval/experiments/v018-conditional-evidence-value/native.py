"""ChatTS native-series vs text-facts reader control; not a retrieval agent."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='2'
os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1';os.environ['TOKENIZERS_PARALLELISM']='false'
from core import save
from gpu import full_reader,parse

HERE=Path(__file__).parent;ROOT=HERE.parents[1];OUT=ROOT/'results/v018-conditional-evidence-value';WORK=HERE.parents[3]


def main():
    assert json.loads((OUT/'audit.complete.json').read_text())['gpu_gate_passed']
    import numpy as np
    import torch
    # Byte-identical frozen copy of the already-used local ChatTS runtime.
    from runtime_frozen import load_local,render_prompt,expand_inputs,decode
    fs={f['id']:f for f in json.loads((OUT/'families-private.json').read_text())}
    es=json.loads((OUT/'reader-episodes-private.json').read_text())
    dest=OUT/'chatts-readers';dest.mkdir(exist_ok=True)
    config={'model':'ChatTS-8B','dtype':'float16','max_new_tokens':256,'decoding':'greedy, fresh per-record KV cache',
        'conditions':['native_raw','facts'],'episodes':len(es),'calls':len(es)*2,
        'manifest_sha256':hashlib.sha256((WORK/'models/chatts-8b/relay-manifest.json').read_bytes()).hexdigest(),
        'runtime_sha256':hashlib.sha256((HERE/'runtime_frozen.py').read_bytes()).hexdigest(),
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    if (dest/'config.json').exists():assert json.loads((dest/'config.json').read_text())==config
    else:save(dest/'config.json',config)
    model,tok,processor=load_local(WORK/'models/chatts-8b',dtype=torch.float16)
    eos=model.generation_config.eos_token_id;eos=[eos] if isinstance(eos,int) else eos
    torch.set_grad_enabled(False);torch.manual_seed(181818)
    records=[];start=time.monotonic()
    for e in es:
        for condition in ['native_raw','facts']:
            target=dest/(e['id']+'-'+condition+'.json')
            if target.exists():records.append(json.loads(target.read_text()));continue
            text,arrays,numeric=full_reader(fs[e['family']],e,facts=condition=='facts',native=True)
            prompt=render_prompt(tok,text);beg=time.monotonic();torch.cuda.reset_peak_memory_stats()
            if condition=='native_raw':
                assert text.count('<ts><ts/>')==len(arrays)
                batch=processor(text=[prompt],timeseries=[np.array(x,dtype=float) for x in arrays],padding=True,return_tensors='pt')
            else:batch=tok([prompt],return_tensors='pt',padding=True)
            batch={k:v.to('cuda:0') for k,v in batch.items()}
            with torch.inference_mode():
                prepared=expand_inputs(model,batch);result=decode(model,prepared,max_new_tokens=256,eos_ids=eos,use_cache=True)
            raw=tok.decode(result['tokens'],skip_special_tokens=True)
            r={'episode':e,'condition':condition,'raw':raw,'parsed':parse(raw),'numeric':numeric,
               'truth':'YES' if e['ys'][e['source']]==0 else 'NO','tokens':result['tokens'],
               'stopped_on_eos':result['stopped_on_eos'],'seconds':time.monotonic()-beg,
               'input_positions':prepared.embeddings.shape[1],'peak_allocated_bytes':torch.cuda.max_memory_allocated(),
               'prompt':text,'series':arrays if condition=='native_raw' else [],
               'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest()}
            save(target,r);records.append(r)
            if len(records)%24==0:print(json.dumps({'model':'chatts','done':len(records),'total':576,'seconds':round(time.monotonic()-start,1)}),flush=True)
            del batch,prepared,result
    save(dest/'records.json',records)
    save(dest/'complete.json',{'complete':True,'records':len(records),'seconds':time.monotonic()-start})


if __name__=='__main__':main()
