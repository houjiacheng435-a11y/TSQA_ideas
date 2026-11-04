"""无标签推理入口：只读取原始.npy、原始问题和公开任务/采样周期。"""
import argparse
import json
import numpy as np
import torch
from model import FrozenText
from evaluate import load_model
from data import serialize_span


@torch.no_grad()
def predict(checkpoint,signal,question,task,dt=6.):
    model,config=load_model(checkpoint);text=FrozenText().cuda()
    x=torch.as_tensor(signal,dtype=torch.float32,device='cuda')
    if x.ndim==1:x=x[:,None]
    if x.shape[1]!=1:raise ValueError('当前官方UK-DALE主电表为单通道；多变量编码器需要另行适配，不静默截断。')
    output=model(x[None],torch.tensor([len(x)],device='cuda'),torch.tensor([dt],device='cuda'),text([question]),intervention=config.get('control'))
    answer=('Yes' if output['output']['existence'][0]>=0 else 'No') if task=='existence' else serialize_span(output['output']['localization'][0].cpu(),len(x)*dt)
    return dict(answer=answer,grid_seconds=(output['grid'][0]*(len(x)-1)*dt).cpu().tolist())


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('checkpoint');parser.add_argument('signal');parser.add_argument('question');parser.add_argument('--task',choices=['existence','localization'],required=True);parser.add_argument('--dt',type=float,default=6.)
    args=parser.parse_args();print(json.dumps(predict(args.checkpoint,np.load(args.signal),args.question,args.task,args.dt),ensure_ascii=False))
