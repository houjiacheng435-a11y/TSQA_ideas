"""官方QA损失与仅在训练阶段读取标注的密度代理；答案区间不等于完整证据。"""
import math
import torch
from torch.nn import functional as F


def span_iou(prediction,target):
    intersection=(torch.minimum(prediction[:,1],target[:,1])-torch.maximum(prediction[:,0],target[:,0])).clamp_min(0)
    union=(prediction[:,1]-prediction[:,0])+(target[:,1]-target[:,0])-intersection
    return intersection/union.clamp_min(1e-8)


def qa_loss(output,target,lengths):
    existence=target['task']==0;localization=~existence
    zero=output['existence'].sum()*0
    le=F.binary_cross_entropy_with_logits(output['existence'][existence],target['yes'][existence]) if existence.any() else zero
    if localization.any():
        pred,truth=output['localization'][localization],target['span'][localization]
        delta=1/lengths[localization,None].float()
        error=(pred-truth).abs()
        huber=torch.where(error<delta,error.square()/(2*delta),error-delta/2).mean()
        ll=huber+(1-span_iou(pred,truth)).mean()
    else:ll=zero
    # 按样本加权，混合批次与单任务批次使用同一目标。
    total=(le*existence.sum()+ll*localization.sum())/len(lengths)
    return total,dict(existence=le,localization=ll)


def proxy_density(intervals,length,dt,kind='boundary_context'):
    """训练标签派生代理：均匀探索质量20%；负例不调用此函数。"""
    t=torch.arange(length,dtype=torch.float32)*float(dt)
    score=torch.zeros(length)
    for a,b in intervals:
        inside=(t>=a)&(t<b)
        if kind=='interval':score+=inside.float()
        elif kind=='boundary_context':
            score+=inside.float()+2*(((t-a).abs()<=60)|((t-b).abs()<=60)).float()
        elif kind=='multi_region':
            score+=inside.float()+(((t>=a-120)&(t<b+120))).float()
        else:raise ValueError(kind)
    if score.sum()==0:return None
    return .8*score/score.sum()+.2/length


def density_loss(p,target,lengths):
    active=target['proxy_valid']
    if not active.any():return p.sum()*0
    q=target['proxy'][active];pp=p[active]
    return (q*(q.clamp_min(1e-30).log()-pp.clamp_min(1e-30).log())).sum(-1).mean()


def coverage_loss(p,lengths):
    """仅惩罚有效支持小于16点的塌缩；默认权重为零，不要求全局均匀。"""
    entropy=-(p*p.clamp_min(1e-30).log()).sum(-1)
    minimum=torch.minimum(lengths.float(),torch.full_like(lengths.float(),16)).log()
    return (minimum-entropy).clamp_min(0).square().mean()
