"""独立训练之外的冻结答案头干预、Query依赖性和可视化。"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import torch

from data import OfficialDataset,collate,to_device,signal_path
from evaluate import evaluate,load_model
from paths import HERE


@torch.no_grad()
def diagnostics(checkpoint,group='test'):
    model,config=load_model(checkpoint);dataset=OfficialDataset(group);folder=Path(checkpoint).parent
    results={}
    for mode in (None,'zero','permutation','cross','uniform'):
        output=evaluate(model,dataset,intervention=mode)
        results[mode or 'normal']=output['summary']
        (folder/f'diagnostic_{mode or "normal"}.json').write_text(json.dumps(output,ensure_ascii=False,indent=2))
    records=[]
    for i in range(len(dataset)):
        batch=collate([dataset[i]]);inputs=to_device(batch,'cuda')['inputs']
        normal=model(**inputs)
        alternative=dataset[(i+1)%len(dataset)]['inputs']['query'].to('cuda')[None]
        altered=model(**dict(inputs,query=alternative))
        p=normal['p'][0];pp=altered['p'][0];length=int(inputs['lengths'][0]);times=torch.arange(length,device='cuda')*inputs['dt'][0]
        mask=torch.zeros(length,dtype=torch.bool,device='cuda')
        for a,b in batch['intervals'][0]:mask|=(times>=a)&(times<b)
        records.append(dict(row_id=batch['rows'][0]['row_id'],density_total_variation=float((p-pp).abs().sum()/2),
                            grid_shift_s=float(((normal['grid']-altered['grid']).abs()*(length-1)*inputs['dt'][0]).mean()),
                            original_target_mass=float(p[mask].sum()) if mask.any() else None,
                            changed_query_old_target_mass=float(pp[mask].sum()) if mask.any() else None))
    results['query_dependence']=records
    results['interpretation']='Query置换仅测函数依赖，不是具有新答案/完整证据标注的同信号配对测试，不能称为正确Query Selectivity。冻结答案头干预属于分布外诊断。'
    (folder/'diagnostics.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    return results


@torch.no_grad()
def plots(checkpoint,group='train'):
    model,config=load_model(checkpoint);dataset=OfficialDataset(group);folder=Path(checkpoint).parent
    # 固定展示最先两条定位题与最先两条存在性题，不按成功与否挑选。
    selected=[]
    for task in ('localization','existence'):
        selected += [i for i,r in enumerate(dataset.rows) if r['task_type']==task][:2]
    figure,axes=plt.subplots(len(selected),2,figsize=(14,3*len(selected)),squeeze=False)
    for j,i in enumerate(selected):
        item=dataset[i];batch=collate([item]);inputs=to_device(batch,'cuda')['inputs'];output=model(**inputs)
        length=int(inputs['lengths'][0]);t=np.arange(length)*float(inputs['dt'][0]);x=inputs['x'][0,:,0].cpu().numpy()
        alternative=dataset[(i+1)%len(dataset)]['inputs']['query'].to('cuda')[None]
        switched=model(**dict(inputs,query=alternative))
        ax,ad=axes[j];ax.plot(t,x,lw=.7,color='gray')
        times=(output['grid'][0]*(length-1)*inputs['dt'][0]).cpu().numpy()
        ax.scatter(times,np.interp(times,t,x),s=7,color='tab:blue',label='original query grid')
        changed_times=(switched['grid'][0]*(length-1)*inputs['dt'][0]).cpu().numpy()
        ax.plot(changed_times,np.full_like(changed_times,x.min()-.04*max(float(x.max()-x.min()),1)), '|',color='tab:orange',markersize=4,label='altered query grid')
        ax.legend(fontsize=6,loc='upper right')
        for a,b in item['intervals']:ax.axvspan(a,b,color='tab:green',alpha=.2)
        ax.set_title(item['row']['question'],fontsize=8);ax.set_ylabel('Power (W)');ax.set_xlabel('Window-relative seconds')
        ad.plot(t,output['p'][0].cpu(),label='original query')
        ad.plot(t,switched['p'][0].cpu(),label='another official query (no paired GT)',alpha=.8)
        for a,b in item['intervals']:ad.axvspan(a,b,color='tab:green',alpha=.2)
        ad.set_title('Altered: '+dataset.rows[(i+1)%len(dataset)]['question'],fontsize=7)
        ad.set_ylabel('Probability / native bin');ad.set_xlabel('Window-relative seconds');ad.legend(fontsize=7)
    figure.tight_layout();figure.savefig(folder/f'density_{group}.png',dpi=130);plt.close(figure)
    curve=json.loads((folder/'curve.json').read_text());fig,axes=plt.subplots(1,4,figsize=(16,3.5))
    for key in ('qa','density_kl'):axes[0].plot([r['step'] for r in curve],[r[key] for r in curve],label=key)
    axes[0].legend();axes[0].set_ylabel('Loss')
    axes[1].plot([r['step'] for r in curve],[r['target_occupancy'] if r['target_occupancy'] is not None else np.nan for r in curve]);axes[1].set_ylabel('Target token occupancy')
    axes[2].plot([r['step'] for r in curve],[r['entropy'] for r in curve]);axes[2].set_ylabel('Density entropy (nats)')
    gradient=[r for r in curve if r['qa_density_grad'] is not None]
    axes[3].plot([r['step'] for r in gradient],[r['qa_density_grad'] for r in gradient],marker='.',color='tab:purple')
    axes[3].set_yscale('symlog',linthresh=1e-8);axes[3].set_ylabel('QA → density gradient (sum L2)')
    for ax in axes:ax.set_xlabel('Optimizer updates')
    fig.tight_layout();fig.savefig(folder/'training.png',dpi=130);plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('checkpoint');parser.add_argument('--group',default='test');parser.add_argument('--plot-only',action='store_true')
    args=parser.parse_args()
    if not args.plot_only:diagnostics(args.checkpoint,args.group)
    plots(args.checkpoint,args.group)
