"""固定官方子集的端到端训练；三种监督条件总更新数一致，Test不参与训练选择。"""
import argparse
import hashlib
import json
import random
import time
from pathlib import Path

import numpy as np
import torch
from data import OfficialDataset,collate,to_device,groups,signal_path
from model import QSample
from losses import qa_loss,density_loss,coverage_loss
from evaluate import evaluate,load_model
from paths import HERE


def seed_all(seed):
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark=False
    torch.use_deterministic_algorithms(True,warn_only=True)


def run(config):
    name=config['name'];folder=HERE/'results'/name;folder.mkdir(parents=True,exist_ok=True)
    config_path=folder/'config.json'
    if config_path.exists():assert json.loads(config_path.read_text())==config,'禁止静默覆盖不同实验配置'
    config_path.write_text(json.dumps(config,ensure_ascii=False,indent=2))
    checkpoint=folder/'final.pt'
    if checkpoint.exists():print(name,'已完成，跳过',flush=True);return
    source_hashes={file.name:hashlib.sha256(file.read_bytes()).hexdigest() for file in HERE.glob('*.py')}
    (folder/'source_hashes.json').write_text(json.dumps(source_hashes,indent=2))
    seed_all(config['seed']);torch.set_num_threads(4);device='cuda'
    train=OfficialDataset(config.get('train_group','train'),config.get('proxy_kind','boundary_context'),config.get('safe_only',False))
    validation_group=config.get('validation_group','validation')
    validation=None
    if all(signal_path(r).exists() for r in groups()[validation_group]):validation=OfficialDataset(validation_group)
    model=QSample(tokens=config['tokens'],method=config['method'],time_mode=config['time_mode']).to(device)
    if config.get('control'):
        trained,_=load_model(config['sampler_checkpoint']);model.load_state_dict(trained.state_dict())
        # 独立初始化匹配答案头；冻结已训练采样器，不能以一次OOD置零替代此训练。
        from model import TimeReadout
        model.readout=TimeReadout(time_mode=config['time_mode']).to(device)
        for parameter in list(model.encoder.parameters())+list(model.film.parameters())+list(model.density.parameters()):parameter.requires_grad_(False)
    optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=config['lr'],weight_decay=1e-4)
    rng=np.random.default_rng(config['seed']);curve=[];torch.cuda.reset_peak_memory_stats();started=time.perf_counter()
    initial=evaluate(model,train,intervention=config.get('control'));(folder/'initial_train.json').write_text(json.dumps(initial,ensure_ascii=False,indent=2))
    length_groups={length:[i for i,r in enumerate(train.rows) if round(r['context_length_s']/r['dt_s'])==length] for length in sorted(set(round(r['context_length_s']/r['dt_s']) for r in train.rows))}
    for step in range(1,config['steps']+1):
        model.train();optimizer.zero_grad(set_to_none=True)
        length=sorted(length_groups)[(step-1)%len(length_groups)]
        ids=rng.choice(length_groups[length],config['batch_size'],replace=len(length_groups[length])<config['batch_size'])
        batch=collate([train[int(i)] for i in ids]);moved=to_device(batch,device)
        # AMP只用于卷积/注意力；密度归一化、CDF与插值在模型内固定FP32。
        with torch.autocast('cuda',dtype=torch.bfloat16,enabled=config.get('amp',True)):
            result=model(**moved['inputs'],intervention=config.get('control'))
        qa,parts=qa_loss(result['output'],moved['targets'],moved['inputs']['lengths'])
        kl=density_loss(result['p'],moved['targets'],moved['inputs']['lengths'])
        cov=coverage_loss(result['p'],moved['inputs']['lengths'])
        warm=config['regime']=='warmup' and step<=config['warmup_steps']
        weight=config['density_weight'] if config['regime']=='joint' or warm else 0.
        loss=qa*(0. if warm else 1.)+weight*kl+config.get('coverage_weight',0.)*cov
        if not torch.isfinite(loss):raise FloatingPointError(f'{name} step{step}: {loss}')
        qa_grad=None
        if step==1 or step%50==0:
            parameters=[p for p in model.density.parameters() if p.requires_grad]
            if parameters:
                gradients=torch.autograd.grad(qa,parameters,retain_graph=True,allow_unused=True)
                qa_grad=sum(float(g.float().norm()) for g in gradients if g is not None)
        loss.backward();norm=float(torch.nn.utils.clip_grad_norm_(model.parameters(),5.));optimizer.step()
        p=result['p'].detach();entropy=float(-(p*p.clamp_min(1e-30).log()).sum(-1).mean())
        grids=result['grid'].detach();hits=[]
        for i,intervals in enumerate(batch['intervals']):
            if intervals:
                t=grids[i]*(moved['inputs']['lengths'][i]-1)*moved['inputs']['dt'][i]
                hit=torch.zeros_like(t,dtype=torch.bool)
                for a,b in intervals:hit|=(t>=a)&(t<b)
                hits.append(float(hit.float().mean()))
        record=dict(step=step,total=float(loss.detach()),qa=float(qa.detach()),existence=float(parts['existence'].detach()),localization=float(parts['localization'].detach()),density_kl=float(kl.detach()),entropy=entropy,max_density=float(p.max(-1).values.mean()),target_occupancy=float(np.mean(hits)) if hits else None,gradient_norm=norm,qa_density_grad=qa_grad,warmup=warm)
        curve.append(record)
        if step%100==0 or step==1 or step==config['steps']:
            print(name,step,{k:round(record[k],4) for k in ('total','qa','density_kl','entropy')},flush=True)
        if config.get('retention_probe') and step==config['warmup_steps']:
            snapshot=evaluate(model,train)
            (folder/'warmup_train.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2))
        if step%config.get('eval_every',200)==0 or step==config['steps']:
            if validation is None and all(signal_path(r).exists() for r in groups()[validation_group]):validation=OfficialDataset(validation_group)
            if validation is not None:
                val=evaluate(model,validation,intervention=config.get('control'));(folder/f'validation_{step}.json').write_text(json.dumps(val,ensure_ascii=False,indent=2))
            else:print(name,'验证窗口待下载；配置固定，不影响训练更新或最终checkpoint选择',flush=True)
            (folder/'curve.json').write_text(json.dumps(curve,ensure_ascii=False))
    trained=evaluate(model,train,intervention=config.get('control'));(folder/'final_train.json').write_text(json.dumps(trained,ensure_ascii=False,indent=2))
    torch.save(dict(state={k:v.cpu() for k,v in model.state_dict().items()},config=config),checkpoint)
    (folder/'resource.json').write_text(json.dumps(dict(seconds=time.perf_counter()-started,peak_allocated_mib=torch.cuda.max_memory_allocated()/2**20,peak_reserved_mib=torch.cuda.max_memory_reserved()/2**20,parameters=sum(p.numel() for p in model.parameters()),train_n=len(train),validation_n=len(validation) if validation is not None else 0,updates=config['steps'],amp='bfloat16' if config.get('amp',True) else 'float32',torch=torch.__version__,gpu=torch.cuda.get_device_name()),indent=2))
    (folder/'curve.json').write_text(json.dumps(curve,ensure_ascii=False));print(name,'完成',flush=True)


def configuration(name,method='adaptive',regime='joint',seed=7,**kwargs):
    config=dict(name=name,method=method,regime=regime,seed=seed,tokens=128,time_mode='absolute',steps=400,warmup_steps=100,batch_size=8,lr=.001,density_weight=1.,coverage_weight=0.,proxy_kind='boundary_context',amp=True)
    config.update(kwargs);return config


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config');parser.add_argument('--overfit',action='store_true')
    args=parser.parse_args()
    config=json.loads(Path(args.config).read_text()) if args.config else configuration('overfit32',steps=800,train_group='overfit',validation_group='overfit',eval_every=200)
    run(config)
