"""生成真实结果的辅助表与图；不更新模型，不改变测试集。"""
import json
from collections import Counter
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from paths import HERE


def main():
    summary=json.loads((HERE/'results/seed_summary.json').read_text())
    def cell(item,key,percent=False,digits=2):
        value=item.get(key)
        if not value:return '—'
        factor=100 if percent else 1
        return f"{value['mean']*factor:.{digits}f} ± {value['std']*factor:.{digits}f}"
    lines=['| 方法/监督 | 正例Acc % | 负例Acc % | 定位Hit % | 定位Occupancy % | 干扰Occupancy % |','|---|---:|---:|---:|---:|---:|']
    for method,regime in sorted(set((r['method'],r['regime']) for r in summary)):
        e=next(r for r in summary if (r['method'],r['regime'],r['task'])==(method,regime,'existence'))
        l=next(r for r in summary if (r['method'],r['regime'],r['task'])==(method,regime,'localization'))
        lines.append(f"|{method}/{regime}|{cell(e,'positive_accuracy',True)}|{cell(e,'negative_accuracy',True)}|{cell(l,'target_hit',True)}|{cell(l,'target_occupancy',True)}|{cell(l,'distractor_occupancy',True)}|")
    (HERE/'results/sampling_table.md').write_text('\n'.join(lines)+'\n')
    lines=['| 固定seed7条件 | Existence Acc % | Balanced Acc % | Localization Acc % | Mean IoU | Endpoint MAE秒 |','|---|---:|---:|---:|---:|---:|']
    for name in ('adaptive_joint_s7','coordinate_only','query_only','adaptive_joint_signal','adaptive_joint_gaps','adaptive_joint_source_safe'):
        d=json.loads((HERE/'results'/name/'test.json').read_text())['summary'];e=d['existence'];l=d['localization']
        lines.append(f"|{name}|{e['accuracy']*100:.2f}|{e['balanced_accuracy']*100:.2f}|{l['accuracy']*100:.2f}|{l['iou']:.4f}|{l['endpoint_mae_s']:.2f}|")
    (HERE/'results/control_table.md').write_text('\n'.join(lines)+'\n')
    lines=['| 方法/种子 | 预热100步定位占比 % | QA微调后400步占比 % |','|---|---:|---:|']
    for method in ('adaptive','blind'):
        for seed in (7,11,23):
            folder=HERE/'results'/f'retention_{method}_s{seed}'
            before=json.loads((folder/'warmup_train.json').read_text())['summary']['localization']['target_occupancy']
            after=json.loads((folder/'final_train.json').read_text())['summary']['localization']['target_occupancy']
            lines.append(f'|{method}/{seed}|{before*100:.2f}|{after*100:.2f}|')
    (HERE/'results/retention_table.md').write_text('\n'.join(lines)+'\n')
    lines=['| 冻结Joint seed7答案头干预 | Existence Acc % | Localization Acc % | Mean IoU |','|---|---:|---:|---:|']
    d=json.loads((HERE/'results/adaptive_joint_s7/diagnostics.json').read_text())
    for name in ('normal','zero','permutation','cross','uniform'):
        e=d[name]['existence'];l=d[name]['localization']
        lines.append(f"|{name}|{e['accuracy']*100:.2f}|{l['accuracy']*100:.2f}|{l['iou']:.4f}|")
    (HERE/'results/intervention_table.md').write_text('\n'.join(lines)+'\n')
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    for task,ax in zip(('existence','localization'),axes):
        for row in [r for r in summary if r['task']==task]:
            x=row['target_occupancy'];y=row['accuracy']
            ax.errorbar(x['mean']*100,y['mean']*100,xerr=x['std']*100,yerr=y['std']*100,fmt='o',capsize=2)
            ax.annotate(row['method']+'/'+row['regime'],(x['mean']*100,y['mean']*100),fontsize=7,xytext=(3,3),textcoords='offset points')
        ax.set_title(task+' (3 seeds; fixed small official Test)');ax.set_xlabel('Target token occupancy (%)');ax.set_ylabel('Official QA accuracy (%)')
    fig.tight_layout();fig.savefig(HERE/'results/accuracy_vs_occupancy.png',dpi=150);plt.close(fig)
    long=[]
    for folder in sorted((HERE/'results').glob('long_*')):
        if not (folder/'test.json').exists():continue
        c=json.loads((folder/'config.json').read_text());d=json.loads((folder/'test.json').read_text())['summary']
        long.append(dict(tokens=c['tokens'],method=c['method'],existence=d['existence'],localization=d['localization']))
    if long:
        lines=['| N | 方法 | Existence Acc % | Balanced Acc % | Localization Acc % | Mean IoU | Loc Hit % | Loc Occupancy % |','|---:|---|---:|---:|---:|---:|---:|---:|']
        for r in sorted(long,key=lambda r:(r['tokens'],r['method'])):
            e,l=r['existence'],r['localization']
            lines.append(f"|{r['tokens']}|{r['method']}|{e['accuracy']*100:.2f}|{e['balanced_accuracy']*100:.2f}|{l['accuracy']*100:.2f}|{l['iou']:.4f}|{l['target_hit']*100:.2f}|{l['target_occupancy']*100:.2f}|")
        (HERE/'results/long_table.md').write_text('\n'.join(lines)+'\n')
    resource=[]
    for p in (HERE/'results').glob('*/resource.json'):
        value=json.loads(p.read_text());value['run']=p.parent.name;resource.append(value)
    (HERE/'results/resources_all.json').write_text(json.dumps(dict(runs=resource,training_seconds_sum=sum(v['seconds'] for v in resource),peak_allocated_mib=max(v['peak_allocated_mib'] for v in resource)),indent=2))


if __name__=='__main__':main()
