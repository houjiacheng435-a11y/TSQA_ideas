"""公开输入与监督标签分离；官方metadata只在数据/损失/评分层使用。"""
import ast
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset

from paths import HERE,CACHE,OFFICIAL
from model import FrozenText
from losses import proxy_density


def hms_seconds(text):
    values=[float(v) for v in text.strip().split(':')]
    assert len(values)==3
    return values[0]*3600+values[1]*60+values[2]


def parse_span(answer):
    a,b=answer.split(' - ')
    return hms_seconds(a),hms_seconds(b)


def serialize_span(pair,duration):
    def hms(t):
        t=int(round(float(t)))
        return f'{t//3600:02d}:{t//60%60:02d}:{t%60:02d}'
    a,b=[float(np.clip(t,0,1))*duration for t in pair]
    return hms(a)+' - '+hms(b)


def official_scorer():
    folder=OFFICIAL/'src/datasets/capture24_haystack/utils'
    namespace={}
    exec(compile((folder/'timestamp_utils.py').read_text(),str(folder/'timestamp_utils.py'),'exec'),namespace)
    tree=ast.parse((folder/'answer_evaluation.py').read_text())
    tree.body=[node for node in tree.body if not (isinstance(node,ast.ImportFrom) and (node.module or '').startswith('src.'))]
    exec(compile(tree,str(folder/'answer_evaluation.py'),'exec'),namespace)
    return namespace['evaluate_answer']


def signal_path(row):
    return CACHE/'reconstructed'/(hashlib.sha256(row['row_id'].encode()).hexdigest()+'.npy')


def groups():return json.loads((HERE/'data_plan.json').read_text())['groups']


@torch.no_grad()
def prepare_embeddings(device='cuda'):
    rows={r['row_id']:r for collection in groups().values() for r in collection}
    questions=sorted(set(row['question'] for row in rows.values()))
    encoder=FrozenText().to(device)
    embeddings=[]
    for start in range(0,len(questions),32):embeddings.append(encoder(questions[start:start+32]).cpu())
    document=dict(questions=questions,embeddings=torch.cat(embeddings),max_length=96,model='prajjwal1/bert-tiny',
                  revision=__import__('paths').TEXT_REVISION)
    path=CACHE/'v5_text_embeddings.pt'
    torch.save(document,path)
    print(f'{len(questions)} 条原始Query编码完成，{path}',flush=True)
    return path


class OfficialDataset(Dataset):
    def __init__(self,group,proxy_kind='boundary_context',safe_only=False):
        self.rows=groups()[group] if isinstance(group,str) else group
        if safe_only:self.rows=[r for r in self.rows if r['source_week_safe']]
        blob=torch.load(CACHE/'v5_text_embeddings.pt',map_location='cpu',weights_only=True)
        self.embeddings=dict(zip(blob['questions'],blob['embeddings']))
        self.proxy_kind=proxy_kind
        for row in self.rows:
            if not signal_path(row).exists():raise FileNotFoundError(f"尚未重建 {row['row_id']}")

    def __len__(self):return len(self.rows)

    def __getitem__(self,index):
        row=self.rows[index]
        x=torch.from_numpy(np.load(signal_path(row)).copy())[:,None]
        length=len(x);dt=float(row['dt_s']);duration=length*dt
        task=0 if row['task_type']=='existence' else 1
        yes=float(row['answer'].strip().lower()=='yes') if task==0 else 0.
        span=parse_span(row['answer']) if task else (0.,0.)
        # 标注只构造监督与评估区间，不进入inputs。
        needles=json.loads(row['needles_json'])
        difficulty=json.loads(row['difficulty_config_json'])
        target=[n for n in needles if n['appliance']==difficulty['target']]
        intervals=[(n['insert_position_samples']*dt,(n['insert_position_samples']+n['insert_duration_samples'])*dt) for n in target]
        if task:
            answer_intervals=[span]
            if self.proxy_kind!='multi_region':intervals=[span]
            else:
                # 第k次运行需要此前同类事件作为序数证据；仍只是代理证据集合。
                intervals=sorted(intervals)[:int(difficulty['k'])]
        else:answer_intervals=intervals if yes else []
        valid=bool(task or (yes and intervals))
        proxy=proxy_density(intervals,length,dt,self.proxy_kind) if valid else None
        return dict(inputs=dict(x=x,lengths=torch.tensor(length),dt=torch.tensor(dt),query=self.embeddings[row['question']],mask=torch.ones(length)),
                    targets=dict(task=torch.tensor(task),yes=torch.tensor(yes),span=torch.tensor(span)/duration,
                                 proxy=proxy if proxy is not None else torch.zeros(length),proxy_valid=torch.tensor(proxy is not None)),
                    row=row,intervals=answer_intervals,distractors=[(n['insert_position_samples']*dt,(n['insert_position_samples']+n['insert_duration_samples'])*dt) for n in needles if n['appliance']!=difficulty['target']])


def collate(items):
    maximum=max(int(item['inputs']['lengths']) for item in items)
    inputs={}
    for key in ('x','mask'):
        values=[]
        for item in items:
            tensor=item['inputs'][key];pad=(0,0,0,maximum-len(tensor)) if key=='x' else (0,maximum-len(tensor))
            values.append(torch.nn.functional.pad(tensor,pad))
        inputs[key]=torch.stack(values)
    for key in ('lengths','dt','query'):inputs[key]=torch.stack([item['inputs'][key] for item in items])
    targets={key:torch.stack([item['targets'][key] for item in items]) for key in ('task','yes','span','proxy_valid')}
    targets['proxy']=torch.stack([torch.nn.functional.pad(item['targets']['proxy'],(0,maximum-len(item['targets']['proxy']))) for item in items])
    return dict(inputs=inputs,targets=targets,rows=[i['row'] for i in items],intervals=[i['intervals'] for i in items],distractors=[i['distractors'] for i in items])


def to_device(batch,device):
    return {group:{k:v.to(device) for k,v in batch[group].items()} for group in ('inputs','targets')}


if __name__=='__main__':prepare_embeddings()
