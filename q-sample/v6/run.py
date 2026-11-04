"""聚焦定位瓶颈：固定预算训练、原生位置/稀疏Pointer与无波形Oracle对照。"""
import argparse
import csv
import hashlib
import json
import os
import random
import time
from pathlib import Path

import numpy as np
import torch
from dataset import Dataset
from network import Model,losses
from legacy import HERE,v5_data,v5_losses

# 两阶段同一矩阵，避免按验证表现选择性报告。
CASES=[('full','regression',False,False),('full','pointer',False,False),
       ('oracle','regression',False,False),('oracle','pointer',False,False),
       ('oracle','regression',False,True),('oracle','pointer',False,True),
       ('uniform','regression',False,False),('uniform','pointer',False,False),
       ('adaptive','regression',False,False),('adaptive','pointer',False,False),
       ('adaptive','regression',True,False),('adaptive','pointer',True,False),
       ('blind','pointer',True,False),
       ('oracle_block','pointer',False,False),('oracle_block','pointer',False,True),('adaptive_noclip','pointer',False,False),('adaptive_noclip','pointer',True,False)]


def case_name(case):
    method,head,joint,zero=case
    return method+'_'+head+('_joint' if joint else '_qa')+('_coordinate' if zero else '')


def buckets(dataset):
    return {length:[i for i,item in enumerate(dataset.items) if len(item['x'])==length] for length in sorted({len(i['x']) for i in dataset.items})}


def maximum_iou(times,ends,span):
    start=times[:,:,None];end=ends[:,None,:]
    intersection=(torch.minimum(end,span[:,1,None,None])-torch.maximum(start,span[:,0,None,None])).clamp_min(0)
    union=end-start+span[:,1,None,None]-span[:,0,None,None]-intersection
    iou=intersection/union.clamp_min(1e-8)
    mask=torch.arange(times.shape[1],device=times.device)[:,None]<=torch.arange(times.shape[1],device=times.device)[None,:]
    return iou.masked_fill(~mask,0).flatten(1).max(-1).values


@torch.no_grad()
def evaluate(model,dataset,case):
    method,head,joint,zero=case;model.eval();rows=[];scorer=v5_data.official_scorer()
    for length,ids in buckets(dataset).items():
        for offset in range(0,len(ids),8):
            inputs,labels,items=dataset.batch(ids[offset:offset+8])
            output=model(**inputs,oracle_grid=labels['oracle_block' if method=='oracle_block' else 'oracle'] if method.startswith('oracle') else None,zero=zero)
            span=output.get('prediction',output['span']);truth=labels['span'];dt=inputs['dt'];duration=inputs['lengths']*dt
            iou=v5_losses.span_iou(span,truth)
            if method=='full':capacity=torch.ones(len(items),device='cuda')
            else:capacity=maximum_iou(output['times'],output['ends'],truth)
            nearest=.5*((output['times']-truth[:,:1]).abs().min(-1).values+(output['ends']-truth[:,1:]).abs().min(-1).values)*duration
            for i,item in enumerate(items):
                row=item['row'];seconds=output['times'][i]*duration[i];a,b=(truth[i]*duration[i]).tolist()
                hit=(seconds>=a)&(seconds<b);prior_hits=[]
                for pa,pb in item['prior']:prior_hits.append(bool(((seconds>=pa)&(seconds<pb)).any()))
                prediction=v5_data.serialize_span(span[i].cpu(),float(duration[i]))
                correct=scorer(row['answer'],prediction,row['answer_type'],iou_threshold=.25,timestamp_tolerance_s=6)['correct']
                import re
                k=int(re.search(r'\b(\d+)(?:st|nd|rd|th)\b',row['question']).group(1))
                rows.append(dict(row_id=row['row_id'],question=row['question'],answer=row['answer'],prediction=prediction,
                                 length=length,correct=bool(correct),iou=float(iou[i]),endpoint_mae_s=float((span[i]-truth[i]).abs().mean()*duration[i]),
                                 target_hit=bool(hit.any()),target_occupancy=float(hit.float().mean()),prefix_coverage=float(np.mean(prior_hits)) if prior_hits else None,
                                 grid_max_iou=float(capacity[i]),nearest_boundary_mae_s=float(nearest[i]),duration_s=b-a,k=k))
    def summary(selected):
        result=dict(n=len(selected))
        for key in ('correct','iou','endpoint_mae_s','target_hit','target_occupancy','prefix_coverage','grid_max_iou','nearest_boundary_mae_s'):
            values=[r[key] for r in selected if r[key] is not None];result['accuracy' if key=='correct' else key]=float(np.mean(values)) if values else None
        result['grid_iou25_capacity']=float(np.mean([r['grid_max_iou']>=.25 for r in selected])) if selected else None
        return result
    grouped={label:summary([r for r in rows if predicate(r)]) for label,predicate in [('L1200',lambda r:r['length']==1200),('L5400',lambda r:r['length']==5400),('short_le60s',lambda r:r['duration_s']<=60),('k1',lambda r:r['k']==1),('k_ge2',lambda r:r['k']>=2)]}
    return dict(summary=summary(rows),strata=grouped,records=rows)


def train(case,stage,steps,seed=7):
    name=stage+'_'+case_name(case);output_dir=HERE/'results';checkpoint_dir=HERE/'checkpoints';checkpoint_dir.mkdir(exist_ok=True)
    checkpoint=checkpoint_dir/(name+'.pt');record_path=output_dir/(name+'.json')
    if checkpoint.exists() and record_path.exists():print(name,'已完成，跳过',flush=True);return
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
    torch.set_num_threads(4);torch.backends.cudnn.benchmark=False
    dataset=Dataset('overfit' if stage=='overfit' else 'train');validation=dataset if stage=='overfit' else Dataset('validation')
    method,head,joint,zero=case;model=Model('oracle' if method=='oracle_block' else method,head).cuda()
    optimizer=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=1e-4)
    rng=np.random.default_rng(seed);by_length=buckets(dataset);curve=[];started=time.perf_counter();torch.cuda.reset_peak_memory_stats()
    initial=evaluate(model,dataset,case)['summary'] if stage=='overfit' else None
    for step in range(1,steps+1):
        model.train();optimizer.zero_grad(set_to_none=True)
        length=sorted(by_length)[(step-1)%len(by_length)];count=8 if stage=='overfit' else 16
        chosen=rng.choice(by_length[length],count,replace=len(by_length[length])<count)
        inputs,labels,_=dataset.batch(chosen)
        with torch.autocast('cuda',dtype=torch.bfloat16):output=model(**inputs,oracle_grid=labels['oracle_block' if method=='oracle_block' else 'oracle'] if method.startswith('oracle') else None,zero=zero)
        loss,parts=losses(output,labels['span'],inputs['lengths'],labels['proxy'],joint)
        if not torch.isfinite(loss):raise FloatingPointError((name,step,float(loss)))
        loss.backward();gradient=float(torch.nn.utils.clip_grad_norm_(model.parameters(),5.));optimizer.step()
        curve.append(dict(step=step,loss=float(loss.detach()),**{k:float(v.detach()) for k,v in parts.items()},gradient=gradient))
        if step==1 or step%200==0:print(name,step,{k:round(float(v.detach()),4) for k,v in parts.items()},flush=True)
    result=dict(case=case,name=name,stage=stage,seed=seed,steps=steps,train_n=len(dataset),validation_n=len(validation),initial_train=initial,
                train=evaluate(model,dataset,case),validation=evaluate(model,validation,case),curve=curve,
                seconds=time.perf_counter()-started,peak_mib=torch.cuda.max_memory_allocated()/2**20,
                parameters=sum(p.numel() for p in model.parameters()),source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob('*.py')})
    record_path.write_text(json.dumps(result,ensure_ascii=False))
    torch.save(dict(state=model.state_dict(),case=case),checkpoint)
    print(name,'完成',result['train']['summary'],result['validation']['summary'],flush=True)


def summarize():
    rows=[]
    for p in sorted((HERE/'results').glob('overfit_*.json'))+sorted((HERE/'results').glob('main_*.json')):
        result=json.loads(p.read_text());row={k:result[k] for k in ('name','stage','train_n','validation_n','steps','seconds','peak_mib')}
        row.update({'train_'+k:v for k,v in result['train']['summary'].items()});row.update({'val_'+k:v for k,v in result['validation']['summary'].items()});rows.append(row)
    if rows:
        with (HERE/'results/summary.csv').open('w') as handle:
            writer=csv.DictWriter(handle,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['overfit','main'],default='overfit');parser.add_argument('--case',type=int);parser.add_argument('--steps',type=int);parser.add_argument('--summarize',action='store_true');args=parser.parse_args()
    if args.summarize:summarize()
    else:
        for case in CASES if args.case is None else [CASES[args.case]]:
            train(case,args.stage,args.steps or (1000 if args.stage=='overfit' else 2000));summarize()
