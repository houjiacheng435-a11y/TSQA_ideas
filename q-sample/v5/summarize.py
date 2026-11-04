"""从逐题官方评分生成完整表格与跨种子统计，不挑选最佳种子。"""
import csv
import json
from collections import defaultdict
import numpy as np
from paths import HERE


def main():
    rows=[];aggregate=defaultdict(list)
    for folder in sorted((HERE/'results').iterdir()):
        config_path=folder/'config.json';result_path=folder/'test.json'
        if not config_path.exists() or not result_path.exists():continue
        config=json.loads(config_path.read_text());result=json.loads(result_path.read_text())
        for task,metrics in result['summary'].items():
            flat={k:v for k,v in metrics.items() if k!='by_length'}
            row=dict(run=folder.name,method=config['method'],regime=config['regime'],seed=config['seed'],tokens=config['tokens'],time_mode=config['time_mode'],task=task,**flat)
            rows.append(row)
            if folder.name in [f'{config["method"]}_{config["regime"]}_s{s}' for s in (7,11,23)]:aggregate[(config['method'],config['regime'],task)].append(row)
    fields=sorted(set(k for r in rows for k in r))
    with (HERE/'results/all_metrics.csv').open('w') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields,lineterminator="\n");writer.writeheader();writer.writerows(rows)
    summaries=[]
    for (method,regime,task),values in sorted(aggregate.items()):
        item=dict(method=method,regime=regime,task=task,seeds=[v['seed'] for v in values])
        for key in ('accuracy','balanced_accuracy','positive_accuracy','negative_accuracy','iou','endpoint_mae_s','normalized_endpoint_mae','target_hit','target_occupancy','target_mass','distractor_occupancy','entropy'):
            numbers=[v[key] for v in values if v.get(key) is not None]
            if numbers:item[key]=dict(mean=float(np.mean(numbers)),std=float(np.std(numbers,ddof=1)) if len(numbers)>1 else None)
        summaries.append(item)
    (HERE/'results/seed_summary.json').write_text(json.dumps(summaries,indent=2))
    text=['| 方法 / 监督 | Existence Acc | Balanced Acc | Localization Acc | Mean IoU | Endpoint MAE (s) | Loc Target Occupancy |','|---|---:|---:|---:|---:|---:|---:|']
    def cell(item,key,percent=False):
        value=item.get(key)
        if value is None:return '—'
        factor=100 if percent else 1;mean=value['mean']*factor;std=value['std']
        digits=4 if key=='iou' else 2
        return f'{mean:.{digits}f}'+(f' ± {std*factor:.{digits}f}' if std is not None else '')
    for method,regime in sorted(set((r['method'],r['regime']) for r in summaries)):
        ex=next(r for r in summaries if r['method']==method and r['regime']==regime and r['task']=='existence')
        loc=next(r for r in summaries if r['method']==method and r['regime']==regime and r['task']=='localization')
        text.append(f"| {method} / {regime} | {cell(ex,'accuracy',True)} | {cell(ex,'balanced_accuracy',True)} | {cell(loc,'accuracy',True)} | {cell(loc,'iou')} | {cell(loc,'endpoint_mae_s')} | {cell(loc,'target_occupancy',True)} |")
    (HERE/'results/main_table.md').write_text('\n'.join(text)+'\n')
    print('\n'.join(text))


if __name__=='__main__':main()
