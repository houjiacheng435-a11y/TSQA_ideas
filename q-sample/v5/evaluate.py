"""官方评分、连续指标和训练外干预；所有诊断均保留逐题预测。"""
import argparse
import json
from collections import defaultdict

import numpy as np
import torch
from torch.utils.data import DataLoader

from data import OfficialDataset,collate,to_device,official_scorer,serialize_span
from losses import span_iou,qa_loss,density_loss
from model import QSample
from paths import HERE


@torch.no_grad()
def evaluate(model,dataset,device='cuda',intervention=None,batch_size=8):
    model.eval();records=[];evaluate_official=official_scorer()
    loader=DataLoader(dataset,batch_size=batch_size,shuffle=False,collate_fn=collate)
    for batch in loader:
        moved=to_device(batch,device);result=model(**moved['inputs'],intervention=intervention)
        qa,_=qa_loss(result['output'],moved['targets'],moved['inputs']['lengths'])
        kl=density_loss(result['p'],moved['targets'],moved['inputs']['lengths'])
        for i,row in enumerate(batch['rows']):
            duration=float(row['context_length_s']);length=int(moved['inputs']['lengths'][i])
            times=(result['grid'][i]*(length-1)*float(row['dt_s'])).cpu().numpy()
            intervals=batch['intervals'][i]
            hits=np.zeros(len(times),dtype=bool);event_mask=np.zeros(length,dtype=bool)
            for a,b in intervals:
                hits|=(times>=a)&(times<b)
                t=np.arange(length)*row['dt_s'];event_mask|=(t>=a)&(t<b)
            p=result['p'][i,:length].cpu().numpy()
            if intervention=='uniform':p=np.full(length,1/length,dtype=np.float32)
            distractor_hits=np.zeros(len(times),dtype=bool);distractor_mask=np.zeros(length,dtype=bool)
            for a,b in batch['distractors'][i]:
                distractor_hits|=(times>=a)&(times<b)
                distractor_mask|=(np.arange(length)*row['dt_s']>=a)&(np.arange(length)*row['dt_s']<b)
            record=dict(row_id=row['row_id'],task=row['task_type'],question=row['question'],answer=row['answer'],
                        length=length,source_week_safe=row['source_week_safe'],qa=float(qa),density_kl=None if intervention=='uniform' else float(kl),
                        entropy=float(-(p*np.log(np.maximum(p,1e-30))).sum()),max_density=float(p.max()),
                        target_occupancy=float(hits.mean()) if intervals else None,
                        target_hit=float(hits.any()) if intervals else None,
                        target_mass=float(p[event_mask].sum()) if intervals else None,
                        distractor_occupancy=float(distractor_hits.mean()),distractor_mass=float(p[distractor_mask].sum()))
            if row['task_type']=='existence':
                logit=float(result['output']['existence'][i]);answer='Yes' if logit>=0 else 'No'
                record.update(prediction=answer,logit=logit,positive=row['answer'].strip().lower()=='yes')
            else:
                pred=result['output']['localization'][i];truth=moved['targets']['span'][i]
                answer=serialize_span(pred.cpu(),duration)
                record.update(prediction=answer,iou=float(span_iou(pred[None],truth[None])[0]),
                              endpoint_mae_s=float((pred-truth).abs().mean()*duration),normalized_endpoint_mae=float((pred-truth).abs().mean()))
            score=evaluate_official(row['answer'],answer,row['answer_type'],iou_threshold=.25,timestamp_tolerance_s=6)
            record['correct']=bool(score['correct']);records.append(record)
    summary={}
    for task in ('existence','localization'):
        rows=[r for r in records if r['task']==task]
        if not rows:continue
        item=dict(n=len(rows),accuracy=float(np.mean([r['correct'] for r in rows])))
        if task=='existence':
            for flag,name in ((True,'positive_accuracy'),(False,'negative_accuracy')):
                selected=[r['correct'] for r in rows if r['positive']==flag]
                item[name]=float(np.mean(selected)) if selected else None
            rates=[item[n] for n in ('positive_accuracy','negative_accuracy') if item[n] is not None]
            item['balanced_accuracy']=float(np.mean(rates))
            item['positive_n']=sum(r['positive'] for r in rows);item['negative_n']=len(rows)-item['positive_n']
        else:
            for name in ('iou','endpoint_mae_s','normalized_endpoint_mae'):item[name]=float(np.mean([r[name] for r in rows]))
        for name in ('target_hit','target_occupancy','target_mass','distractor_occupancy','distractor_mass','entropy','max_density'):
            valid=[r[name] for r in rows if r[name] is not None]
            item[name]=float(np.mean(valid)) if valid else None
        # 长度分层避免长窗口的秒误差掩盖短窗口行为。
        item['by_length']={str(length):dict(n=sum(r['length']==length for r in rows),accuracy=float(np.mean([r['correct'] for r in rows if r['length']==length]))) for length in sorted(set(r['length'] for r in rows))}
        summary[task]=item
    return dict(summary=summary,records=records)


def load_model(path,device='cuda'):
    payload=torch.load(path,map_location='cpu',weights_only=True)
    config=payload['config'];model=QSample(tokens=config['tokens'],method=config['method'],time_mode=config['time_mode']).to(device)
    model.load_state_dict(payload['state']);model.eval()
    return model,config


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('checkpoint');parser.add_argument('--group',default='validation');parser.add_argument('--intervention');parser.add_argument('--output',required=True)
    args=parser.parse_args();model,config=load_model(args.checkpoint)
    result=evaluate(model,OfficialDataset(args.group),intervention=args.intervention or config.get('control'))
    open(args.output,'w').write(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result['summary'],ensure_ascii=False))
