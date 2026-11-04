"""在v5采样器与时间Transformer上增加定位Pointer；Full支路完全独立。"""
import math
import torch
from torch import nn
from torch.nn import functional as F
from legacy import v5_model,v5_losses


def ordered(pair):
    pair=pair.float().sigmoid();start=pair[:,0]
    return torch.stack([start,start+(1-start)*pair[:,1]],-1)


class BoundaryHead(nn.Module):
    def __init__(self,width,kind):
        super().__init__();self.kind=kind
        self.reg=nn.Linear(width,2);self.pointer=nn.Linear(width,2)
    def forward(self,h,pooled,times,lengths,dt):
        ends=(times+1/lengths[:,None].float()).clamp(max=1)
        if self.kind=='regression':return dict(span=ordered(self.reg(pooled)),times=times,ends=ends)
        logits=self.pointer(h).float()
        starts=logits[:,:,0];stops=logits[:,:,1]
        expected=torch.stack([(starts.softmax(-1)*times).sum(-1),(stops.softmax(-1)*ends).sum(-1)],-1)
        expected=expected.sort(-1).values
        # 线性复杂度的有序联合解码，不在原始L上构造L×L张量。
        best_start,start_idx=starts.cummax(-1)
        stop_idx=(best_start+stops).argmax(-1)
        start_idx=start_idx.gather(1,stop_idx[:,None]).squeeze(1)
        prediction=torch.stack([times.gather(1,start_idx[:,None]).squeeze(1),ends.gather(1,stop_idx[:,None]).squeeze(1)],-1)
        return dict(span=expected,prediction=prediction,logits=logits,times=times,ends=ends)


def time_features(values,times,lengths,dt):
    duration=lengths.float()*dt
    gaps=torch.cat([torch.zeros_like(times[:,:1]),times[:,1:]-times[:,:-1]],1)
    gap_seconds=gaps*duration[:,None]
    return torch.stack([values[:,:,0],torch.ones_like(times),times,gaps,torch.log1p(gap_seconds)/torch.log1p(duration[:,None]),torch.log1p(duration[:,None]).expand_as(times)/math.log(86401)],-1)


class SparseReadout(v5_model.TimeReadout):
    def __init__(self,kind):
        super().__init__(width=48,time_mode='absolute')
        # 保留v5完整Transformer；只替换最后的定位解码与损失。
        self.boundary=BoundaryHead(48,kind)
    def forward(self,values,times,lengths,dt,query):
        feature=time_features(values,times,lengths,dt);h=self.project(feature);n=h.shape[1]
        pos=torch.arange(n,device=h.device)[:,None]
        freq=torch.exp(torch.arange(0,48,2,device=h.device)*(-math.log(10000)/48))
        pe=torch.zeros(n,48,device=h.device);pe[:,0::2]=torch.sin(pos*freq);pe[:,1::2]=torch.cos(pos*freq)
        h=h+pe[None]+self.query(query)[:,None]
        h=torch.cat([self.query(query)[:,None],h],1)
        encoded=self.transformer(h)
        return self.boundary(self.norm(encoded[:,1:]),self.norm(encoded[:,0]),times,lengths,dt)


class FullReadout(nn.Module):
    def __init__(self,kind):
        super().__init__()
        self.project=nn.Conv1d(6,48,7,padding=3)
        self.blocks=nn.ModuleList([nn.Conv1d(48,48,5,padding=2*d,dilation=d) for d in (1,4,16)])
        self.query=nn.Linear(128,48)
        self.gru=nn.GRU(48,32,batch_first=True,bidirectional=True)
        self.mix=nn.Linear(112,48);self.norm=nn.LayerNorm(48)
        self.boundary=BoundaryHead(48,kind)
    def forward(self,values,times,lengths,dt,query):
        # Full模型直接编码全部原始观测；不会向稀疏答案头传此特征。
        h=F.gelu(self.project(time_features(values,times,lengths,dt).transpose(1,2)))
        h=h+self.query(query)[:,:,None]
        for layer in self.blocks:h=h+F.gelu(layer(h))
        coarse=F.avg_pool1d(h,4,ceil_mode=True).transpose(1,2)
        # 本机BF16 GRU会走低效路径；只让GRU用FP32的cuDNN实现，卷积/Transformer仍AMP。
        with torch.autocast('cuda',enabled=False):context,_=self.gru(coarse.float())
        context=F.interpolate(context.transpose(1,2),size=h.shape[-1],mode='linear',align_corners=False).transpose(1,2)
        h=self.norm(F.gelu(self.mix(torch.cat([h.transpose(1,2),context],-1))))
        return self.boundary(h,h.mean(1),times,lengths,dt)


class UnclippedSampler(v5_model.QSample):
    """只移除v5硬截断，其余CNN、FiLM、密度下限和逆CDF完全相同。"""
    def distribution(self,x,lengths,query):
        parts=[]
        for i in range(len(x)):
            length=int(lengths[i]);h=self.encoder(x[i:i+1,:length].transpose(1,2)/1000.)
            gamma,beta=self.film(query[i:i+1]).chunk(2,-1)
            h=h*(1+.1*gamma[:,:,None])+beta[:,:,None]
            logits=F.interpolate(self.density(h).float(),size=length,mode='linear',align_corners=False).squeeze(1)
            # FP32 softmax自带数值稳定平移；2%下限继续保证CDF可用。
            p=(1-self.floor)*logits.softmax(-1)+self.floor/length
            parts.append(F.pad(p,(0,x.shape[1]-length)))
        return torch.cat(parts,0)


class Model(nn.Module):
    def __init__(self,method,head):
        super().__init__();self.method=method
        self.semantic=nn.Linear(14,128,bias=False)
        if method=='full':self.readout=FullReadout(head)
        else:
            self.sampler=(UnclippedSampler if method=='adaptive_noclip' else v5_model.QSample)(tokens=128,method='blind' if method=='blind' else 'uniform' if method=='uniform' else 'adaptive')
            self.sampler.readout=nn.Identity()
            self.readout=SparseReadout(head)
    def forward(self,x,lengths,dt,query,semantic,oracle_grid=None,zero=False):
        query=query+self.semantic(semantic)
        p=None
        if self.method=='full':
            if not bool((lengths==x.shape[1]).all()):raise ValueError('Full按原生长度分桶，不能把padding当真实观测')
            times=(torch.arange(x.shape[1],device=x.device)[None]/lengths[:,None]).expand(len(x),-1)
            values=x/1000.;grid=times*lengths[:,None]/(lengths[:,None]-1)
        else:
            if self.method=='oracle':
                if oracle_grid is None:raise ValueError('特权Oracle需要显式标注网格，禁止冒充无标签部署')
                grid=oracle_grid
            else:
                if oracle_grid is not None:raise ValueError('非Oracle不得接收特权网格')
                p=self.sampler.distribution(x,lengths,query)
                grid=v5_model.inverse_cdf(p,128,lengths)
            values=v5_model.sample_linear(x/1000.,grid,lengths)
            times=grid*(lengths[:,None]-1)/lengths[:,None]
        if zero:values=values*0
        result=self.readout(values,times,lengths,dt,query)
        result.update(p=p,grid=grid,values=values)
        return result


def losses(result,span,lengths,proxy,joint=False):
    prediction=result['span'];delta=1/lengths[:,None].float();error=(prediction-span).abs()
    huber=torch.where(error<delta,error.square()/(2*delta),error-delta/2).mean()
    geometry=huber+1-v5_losses.span_iou(prediction,span).mean()
    ce=geometry*0
    if 'logits' in result:
        # 标签索引只用于训练；不向读出器提供GT或对离散目标反传。
        start=(result['times'].detach()-span[:,:1]).abs().argmin(-1)
        end=(result['ends'].detach()-span[:,1:]).abs().argmin(-1)
        ce=.5*(F.cross_entropy(result['logits'][:,:,0],start)+F.cross_entropy(result['logits'][:,:,1],end))
    kl=geometry*0
    if joint:
        p=result['p'];kl=(proxy*(proxy.clamp_min(1e-30).log()-p.clamp_min(1e-30).log())).sum(-1).mean()
    return geometry+ce+kl,dict(geometry=geometry,ce=ce,kl=kl)
