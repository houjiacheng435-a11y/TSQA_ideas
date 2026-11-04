"""只汇总已执行结果，比较解码、坐标表达上限及具体失败；不做模型选择。"""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from legacy import HERE
from run import CASES,case_name,evaluate
from dataset import path,Dataset


def sampler_check():
    """同一已训练权重只改变硬截断，复查梯度；不把替换后的答案计入成绩。"""
    import torch
    from torch.nn import functional as F
    from network import Model,losses
    torch.set_num_threads(4);data=Dataset('overfit');inputs,labels,_=data.batch([0,1,16,17]);checks=[]
    for head,remove_clamp in [('pointer',False),('regression',False),('pointer',True)]:
        name='adaptive_'+head+'_qa'
        payload=torch.load(HERE/'checkpoints'/('overfit_'+name+'.pt'),weights_only=True)
        model=Model('adaptive_noclip' if remove_clamp else 'adaptive',head).cuda();model.load_state_dict(payload['state']);model.eval()
        raw=[]
        with torch.no_grad():
            query=inputs['query']+model.semantic(inputs['semantic'])
            for i in range(4):
                length=int(inputs['lengths'][i]);h=model.sampler.encoder(inputs['x'][i:i+1,:length].transpose(1,2)/1000.)
                gamma,beta=model.sampler.film(query[i:i+1]).chunk(2,-1);h=h*(1+.1*gamma[:,:,None])+beta[:,:,None]
                raw.append(F.interpolate(model.sampler.density(h).float(),size=length,mode='linear',align_corners=False).flatten())
        output=model(**inputs);loss,_=losses(output,labels['span'],inputs['lengths'],labels['proxy'],False)
        gradients=torch.autograd.grad(loss,list(model.sampler.density.parameters()),allow_unused=True)
        logits=torch.cat(raw)
        checks.append(dict(case='same_checkpoint_remove_clamp_only' if remove_clamp else name,indices=[0,1,16,17],
                           logit_min=float(logits.min()),logit_max=float(logits.max()),saturation_fraction=float((logits.abs()>=12).float().mean()),
                           qa_density_grad=sum(float(g.abs().sum()) for g in gradients if g is not None),
                           p_max=output['p'].detach().max(-1).values.tolist(),uniform=(1/inputs['lengths'].float()).tolist(),
                           note='仅检查梯度路径，不把分布外替换后的答案作为训练成绩'))
    (HERE/'results/sampler_check.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))


def main():
    records={}
    for case in CASES:
        for stage in ('overfit','main'):
            file=HERE/'results'/(stage+'_'+case_name(case)+'.json')
            if file.exists():records[stage,case_name(case)]=json.loads(file.read_text())
    lines=['| 方法/头 | 32题Train Acc % | 1024题Train Acc % | Val Acc % | Val IoU | Val端点MAE秒 | 连续锚点通过比例 % |','|---|---:|---:|---:|---:|---:|---:|']
    for case in CASES:
        name=case_name(case)
        if ('main',name) not in records:continue
        over=records['overfit',name]['train']['summary'];large=records['main',name];train=large['train']['summary'];val=large['validation']['summary']
        capacity=f"{val['grid_iou25_capacity']*100:.2f}" if case[1]=='pointer' else '—'
        lines.append(f"|{name}|{over['accuracy']*100:.2f}|{train['accuracy']*100:.2f}|{val['accuracy']*100:.2f}|{val['iou']:.4f}|{val['endpoint_mae_s']:.1f}|{capacity}|")
    (HERE/'results/table.md').write_text('\n'.join(lines)+'\n')
    groups=[('full',False,False),('oracle',False,False),('oracle',False,True),('uniform',False,False),('adaptive',False,False),('adaptive',True,False),('blind',True,False),('oracle_block',False,False),('oracle_block',False,True),('adaptive_noclip',False,False),('adaptive_noclip',True,False)]
    names=['Full','Oracle*','Oracle coord*','Uniform','Adaptive QA','Adaptive Joint','Blind Joint','Block oracle*','Block coord*','NoClip QA','NoClip Joint']
    fig,axes=plt.subplots(1,2,figsize=(17,4.5))
    for ax,stage,subset,title in [(axes[0],'overfit','train','Fixed 32 official training questions'),(axes[1],'main','validation','1024 Train → 128 Validation; no Test')]:
        for head,delta,color in [('regression',-.18,'tab:gray'),('pointer',.18,'tab:blue')]:
            scores=[];caps=[]
            for method,joint,zero in groups:
                key=case_name((method,head,joint,zero));d=records.get((stage,key))
                scores.append(d[subset]['summary']['accuracy']*100 if d else np.nan)
                caps.append(d[subset]['summary']['grid_iou25_capacity']*100 if d and head=='pointer' else np.nan)
            ax.bar(np.arange(len(groups))+delta,scores,width=.34,label=head,color=color)
            if head=='pointer':ax.scatter(np.arange(len(groups))+delta,caps,s=18,color='tab:orange',marker='_',label='pointer coordinate capacity')
        ax.set_xticks(range(len(groups)),names,rotation=55,ha='right',fontsize=8);ax.set_ylim(0,106);ax.set_title(title);ax.set_ylabel('Official IoU≥0.25 accuracy (%)');ax.legend(fontsize=7)
    fig.tight_layout();fig.savefig(HERE/'results/comparison.png',dpi=150);plt.close(fig)
    # 已训练答案头的零波形干预只检查依赖关系，不能当成独立训练的Coordinate-only。
    # 采样器仍读取原始X，故学习网格仍可能携带输入信息；不重训、不选模。
    if len(records)==2*len(CASES):
        sampler_check()
        import torch
        from network import Model
        torch.set_num_threads(4)
        validation=Dataset('validation');interventions=[]
        for method,joint in [('full',False),('uniform',False),('adaptive',False),('adaptive',True),('blind',True),('adaptive_noclip',False),('adaptive_noclip',True)]:
            case=(method,'pointer',joint,False);name=case_name(case)
            model=Model(method,'pointer').cuda()
            payload=torch.load(HERE/'checkpoints'/('main_'+name+'.pt'),weights_only=True)
            model.load_state_dict(payload['state'])
            result=evaluate(model,validation,(method,'pointer',joint,True))
            interventions.append(dict(case=name,normal=records['main',name]['validation']['summary'],zero_signal=result['summary'],
                                      note='分布外干预；相同已训练答案头/网格/Query，仅采样波形置零，不等同独立训练的Coordinate-only'))
        (HERE/'results/interventions.json').write_text(json.dumps(interventions,ensure_ascii=False,indent=2))
    # 预先说明选择规则，保存全部涉及条件的完整验证记录，图只展示两类失败。
    required=['full_pointer_qa','uniform_pointer_qa','adaptive_pointer_joint','oracle_block_pointer_qa']
    if not all(('main',n) in records for n in required):return
    rows={n:{r['row_id']:r for r in records['main',n]['validation']['records']} for n in required}
    selected=[]
    for condition in ('short_grid_failure','ordinal_failure'):
        candidates=[]
        for key,full in rows['full_pointer_qa'].items():
            uniform=rows['uniform_pointer_qa'][key];learned=rows['adaptive_pointer_joint'][key]
            if condition=='short_grid_failure' and full['correct'] and not uniform['correct'] and uniform['grid_max_iou']<.25:candidates.append(key)
            if condition=='ordinal_failure' and full['correct'] and not learned['correct'] and full['k']>=2:candidates.append(key)
        if candidates:selected.append((condition,sorted(candidates)[0]))
    failures=[]
    for label,key in selected:
        failures.append(dict(selection=label,results={n:rows[n][key] for n in required}))
    (HERE/'results/failures.json').write_text(json.dumps(failures,ensure_ascii=False,indent=2))
    if failures:
        plan=json.loads((HERE/'data_plan.json').read_text())['groups']['validation'];metadata={r['row_id']:r for r in plan}
        fig,axes=plt.subplots(len(failures),2,figsize=(15,3.5*len(failures)),squeeze=False,gridspec_kw={'width_ratios':[2,1]})
        from legacy import v5_data
        for pair,failure in zip(axes,failures):
            ax,zoom=pair
            full=failure['results']['full_pointer_qa'];row=metadata[full['row_id']];signal=np.load(path(row));t=np.arange(len(signal))*6
            ax.plot(t,signal,color='gray',lw=.7);truth_a,truth_b=v5_data.parse_span(row['answer']);ax.axvspan(truth_a,truth_b,color='tab:green',alpha=.25,label='official answer')
            for name,color in [('uniform_pointer_qa','tab:orange'),('adaptive_pointer_joint','tab:red')]:
                a,b=v5_data.parse_span(failure['results'][name]['prediction']);ax.axvspan(a,b,color=color,alpha=.15,label=name)
            ax.set_title(failure['selection']+': '+row['question'],fontsize=9);ax.set_xlabel('Window-relative seconds');ax.set_ylabel('Power (W)');ax.legend(fontsize=7)
            # 原始长图中几十秒事件几乎不可见，放大真实边界并显示均匀采样实际观测。
            uniform_t=((np.arange(128)+.5)/128)*(len(signal)-1)*6
            a,b=truth_a,truth_b
            zoom.plot(t,signal,color='gray',lw=.8);zoom.axvspan(a,b,color='tab:green',alpha=.25)
            zoom.scatter(uniform_t,np.interp(uniform_t,t,signal),s=20,color='tab:orange',label='Uniform observed values',zorder=3)
            margin=max(120,(b-a)*.6,len(signal)*6/128)
            zoom.set_xlim(max(0,a-margin),min(len(signal)*6,b+margin));zoom.set_title('True interval and sampled evidence',fontsize=9)
            zoom.set_xlabel('Window-relative seconds');zoom.legend(fontsize=7)
        fig.tight_layout();fig.savefig(HERE/'results/failures.png',dpi=150);plt.close(fig)


if __name__=='__main__':main()
