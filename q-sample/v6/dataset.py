"""官方定位数据：公开问题语义与监督字段分离，全部波形复用官方缓存。"""
import json
import re
import hashlib
import numpy as np
import torch
from legacy import HERE,CACHE,v5_data,v5_losses,v5_model

DEVICES=('dishwasher','fridge_freezer','fridge','hair_dryer','kettle','microwave','oven','toaster','washer_dryer','washing_machine')
ALIASES=(('dishwasher',('dishwasher',)),('fridge_freezer',('fridge-freezer','refrigerator-freezer','fridge freezer','refrigerator freezer')),
         ('washer_dryer',('washer-dryer','washer dryer','washer/dryer')),('washing_machine',('washing machine','washer')),
         ('hair_dryer',('hair dryer','hairdryer')),('microwave',('microwave',)),('fridge',('fridge','refrigerator')),
         ('kettle',('kettle',)),('oven',('oven',)),('toaster',('toaster',)))


def semantics(question):
    """仅从原问题字符串解析公开设备名和序数，不接收metadata。"""
    question=question.lower()
    device=next((name for name,aliases in ALIASES if any(alias in question for alias in aliases)),None)
    match=re.search(r'\b([1-9]\d*)(?:st|nd|rd|th)\b',question)
    if device is None or match is None:raise ValueError('无法解析公开问题：'+question)
    ordinal=int(match.group(1))
    return torch.cat([torch.nn.functional.one_hot(torch.tensor(DEVICES.index(device)),10),torch.nn.functional.one_hot(torch.tensor(ordinal-1),4)]).float()


def path(row):return CACHE/'reconstructed'/(hashlib.sha256(row['row_id'].encode()).hexdigest()+'.npy')


class Dataset:
    def __init__(self,group):
        self.rows=json.loads((HERE/'data_plan.json').read_text())['groups'][group]
        payload=torch.load(CACHE/'v6_text_embeddings.pt',weights_only=True)
        embeddings=dict(zip(payload['questions'],payload['embeddings']))
        self.items=[]
        for row in self.rows:
            x=torch.from_numpy(np.load(path(row)).copy())[:,None];length=len(x);dt=float(row['dt_s'])
            span=torch.tensor(v5_data.parse_span(row['answer']))/(length*dt)
            needles=json.loads(row['needles_json']);difficulty=json.loads(row['difficulty_config_json'])
            # 这部分只用于监督、特权Oracle和离线覆盖评估。
            all_spans=[(n['insert_position_samples']*dt,(n['insert_position_samples']+n['insert_duration_samples'])*dt) for n in needles]
            prior=[(n['insert_position_samples']*dt,(n['insert_position_samples']+n['insert_duration_samples'])*dt) for n in needles if n['appliance']==difficulty['target'] and n['insert_position_samples']*dt<float(span[0])*length*dt-1]
            proxy=v5_losses.proxy_density([tuple((span*length*dt).tolist())],length,dt)
            # 每个插入事件等质量，外扩两个原生点；不指定查询类别或第k次。
            oracle=torch.zeros(length);times=torch.arange(length)*dt
            for a,b in all_spans:
                mask=(times>=max(0,a-2*dt))&(times<min(length*dt,b+2*dt))
                oracle+=mask.float()/mask.sum().clamp_min(1)
            oracle=.8*oracle/oracle.sum()+.2/length
            grid=v5_model.inverse_cdf(oracle[None],128,torch.tensor([length]))[0]
            # 补充Oracle仅给64个固定粗时间格，不暴露格内精确边界。
            cells=(torch.arange(length)*64//length)
            block=torch.zeros(length)
            for a,b in all_spans:
                first=int(a/(length*dt)*64);last=min(63,int(np.ceil(b/(length*dt)*64))-1)
                mask=(cells>=first)&(cells<=last)
                block+=mask.float()/mask.sum().clamp_min(1)
            block=.8*block/block.sum()+.2/length
            block_grid=v5_model.inverse_cdf(block[None],128,torch.tensor([length]))[0]
            self.items.append(dict(x=x,query=embeddings[row['question']],semantic=semantics(row['question']),span=span,
                                   proxy=proxy,oracle=grid,oracle_block=block_grid,row=row,prior=prior))
    def __len__(self):return len(self.items)

    def batch(self,indices,device='cuda'):
        items=[self.items[int(i)] for i in indices];maximum=max(len(i['x']) for i in items)
        x=torch.stack([torch.nn.functional.pad(i['x'],(0,0,0,maximum-len(i['x']))) for i in items])
        lengths=torch.tensor([len(i['x']) for i in items]);dt=torch.tensor([float(i['row']['dt_s']) for i in items])
        values=dict(x=x,lengths=lengths,dt=dt,query=torch.stack([i['query'] for i in items]),semantic=torch.stack([i['semantic'] for i in items]))
        labels=dict(span=torch.stack([i['span'] for i in items]),proxy=torch.stack([torch.nn.functional.pad(i['proxy'],(0,maximum-len(i['proxy']))) for i in items]),oracle=torch.stack([i['oracle'] for i in items]),oracle_block=torch.stack([i['oracle_block'] for i in items]))
        return {k:v.to(device) for k,v in values.items()},{k:v.to(device) for k,v in labels.items()},items
