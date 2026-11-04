"""Q-Sample v5：完整波形只能经过采样器进入答案头。"""
import math
from contextlib import nullcontext

import torch
from torch import nn
from torch.nn import functional as F

from paths import TEXT_DIR


class FrozenText(nn.Module):
    """固定原始自然语言的处理：BERT-tiny、最多96词元、有效位置均值。"""
    def __init__(self):
        super().__init__()
        from transformers import BertModel, BertTokenizerFast
        self.tokenizer = BertTokenizerFast(vocab_file=str(TEXT_DIR/'vocab.txt'), do_lower_case=True)
        self.encoder = BertModel.from_pretrained(TEXT_DIR, local_files_only=True)
        self.encoder.requires_grad_(False).eval()

    @torch.no_grad()
    def forward(self, questions):
        self.encoder.eval()
        batch = self.tokenizer(questions, padding=True, truncation=True, max_length=96, return_tensors='pt')
        batch = {k:v.to(next(self.encoder.parameters()).device) for k,v in batch.items()}
        out = self.encoder(**batch).last_hidden_state
        mask = batch['attention_mask'].unsqueeze(-1)
        return (out*mask).sum(1)/mask.sum(1).clamp_min(1)


def inverse_cdf(probability, tokens, lengths):
    """仅区间索引离散，区间端点与分数均保留梯度；生产关键计算固定FP32。"""
    with torch.autocast(device_type=probability.device.type, enabled=False):
        p = probability.float()
        p = p/p.sum(-1,keepdim=True).clamp_min(1e-30)
        cdf = torch.cat([torch.zeros_like(p[:,:1]),p.cumsum(-1)],-1)
        # 用实际尾值归一化，避免浮点累加误差使最后一个分位点越界。
        cdf = cdf/cdf[:,-1:].clone().clamp_min(1e-30)
        u = (torch.arange(tokens,device=p.device,dtype=torch.float32)+.5)/tokens
        u = u.expand(len(p),-1).contiguous()
        right = torch.searchsorted(cdf.contiguous(),u,right=True)
        right = torch.minimum(right,lengths[:,None]).clamp_min(1)
        left = right-1
        lo,hi = cdf.gather(1,left),cdf.gather(1,right)
        fraction = ((u-lo)/(hi-lo).clamp_min(1e-12)).clamp(0,1)
        # 每个概率质量对应一个等宽时间单元，均匀密度恰好产生均匀中点。
        grid = (left.float()+fraction)/lengths[:,None].float()
        return grid.clamp(0,1)


def sample_linear(x, grid, lengths):
    """x为[B,L,C]；只建立[B,N,C]中间量，不建立[B,N,L]。"""
    with torch.autocast(device_type=x.device.type, enabled=False):
        position = grid.float()*(lengths[:,None]-1).float()
        left = position.floor().long()
        right = torch.minimum(left+1,lengths[:,None]-1)
        idx = left[:,:,None].expand(-1,-1,x.shape[-1])
        a = x.float().gather(1,idx)
        b = x.float().gather(1,right[:,:,None].expand_as(idx))
        return a+(b-a)*(position-left.float())[:,:,None]


class MultiScaleEncoder(nn.Module):
    def __init__(self,width=48):
        super().__init__()
        self.stem = nn.Conv1d(1,width,7,stride=2,padding=3)
        self.branches = nn.ModuleList([nn.Conv1d(width,width,3,padding=d,dilation=d) for d in (1,4,16)])
        self.mix = nn.Conv1d(width*3,width,1)
        self.norm = nn.GroupNorm(8,width)
    def forward(self,x):
        h = F.gelu(self.stem(x))
        h = F.gelu(self.norm(self.mix(torch.cat([F.gelu(c(h)) for c in self.branches],1))))
        # 保留位置，同时限制密度网络代价；非整除长度不进行人为波形重采样。
        return F.adaptive_avg_pool1d(h,min(h.shape[-1],512))


class TimeReadout(nn.Module):
    """只接收采样后的信号、公开时间、观察掩码和Query。"""
    def __init__(self,width=48,time_mode='absolute'):
        super().__init__()
        self.time_mode = time_mode
        self.project = nn.Linear(6,width)
        self.query = nn.Linear(128,width)
        layer = nn.TransformerEncoderLayer(width,4,width*3,dropout=0.,activation='gelu',batch_first=True,norm_first=True)
        self.transformer = nn.TransformerEncoder(layer,2,enable_nested_tensor=False)
        self.norm = nn.LayerNorm(width)
        self.heads = nn.ModuleDict({'existence':nn.Linear(width,1),'localization':nn.Linear(width,2),
                                    'counting':nn.Linear(width,6),'ordering':nn.Linear(width,1)})

    def forward(self,values,grid,lengths,dt,query,observed=None):
        b,n,_ = values.shape
        duration = lengths.float()*dt.float()
        times = grid*(lengths[:,None]-1).float()*dt[:,None]
        gaps = torch.cat([torch.zeros_like(times[:,:1]),times[:,1:]-times[:,:-1]],1)
        obs = torch.ones_like(grid) if observed is None else observed
        absolute = times/duration[:,None]
        relative = gaps/duration[:,None]
        loggap = torch.log1p(gaps)/torch.log1p(duration[:,None])
        if self.time_mode=='signal':absolute,relative,loggap = absolute*0,relative*0,loggap*0
        if self.time_mode=='gaps':absolute = absolute*0
        scale = torch.log1p(duration[:,None]).expand_as(grid)/math.log(86401)
        if self.time_mode=='signal':scale=scale*0
        feature = torch.stack([values[:,:,0],obs,absolute,relative,loggap,scale],-1)
        h = self.project(feature)
        # Token次序编码不携带原序列时间，仅表示压缩序列中的先后。
        pos = torch.arange(n,device=h.device)[:,None]
        freq = torch.exp(torch.arange(0,h.shape[-1],2,device=h.device)*(-math.log(10000)/h.shape[-1]))
        pe = torch.zeros(n,h.shape[-1],device=h.device)
        pe[:,0::2],pe[:,1::2] = torch.sin(pos*freq),torch.cos(pos*freq)
        h = h+pe[None]+self.query(query)[:,None]
        h = torch.cat([self.query(query)[:,None],h],1)
        pooled = self.norm(self.transformer(h)[:,0])
        pair = self.heads['localization'](pooled).sigmoid()
        start = pair[:,0]
        end = start+(1-start)*pair[:,1]
        return {'existence':self.heads['existence'](pooled).squeeze(-1),
                'localization':torch.stack([start,end],-1)}


class QSample(nn.Module):
    def __init__(self,tokens=128,method='adaptive',time_mode='absolute',width=48,floor=.02):
        super().__init__()
        self.tokens,self.method,self.floor = tokens,method,floor
        self.encoder = MultiScaleEncoder(width)
        self.film = nn.Linear(128,width*2)
        self.density = nn.Sequential(nn.Conv1d(width,width,1),nn.GELU(),nn.Conv1d(width,1,1))
        self.readout = TimeReadout(width,time_mode)

    def distribution(self,x,lengths,query):
        parts=[]
        for i in range(len(x)):
            length=int(lengths[i]);signal=x[i:i+1,:length].transpose(1,2)/1000.
            if self.method=='uniform':p=torch.ones(1,length,device=x.device)/length
            elif self.method=='saliency':
                mean=F.avg_pool1d(signal,9,stride=1,padding=4)
                var=(F.avg_pool1d(signal.square(),9,stride=1,padding=4)-mean.square()).clamp_min(0)
                difference=F.pad((signal[:,:,1:]-signal[:,:,:-1]).abs(),(1,0))
                score=var.sqrt()+difference+.001
                p=(score/score.sum(-1,keepdim=True)).squeeze(1)
            else:
                h=self.encoder(signal)
                q=query[i:i+1] if self.method!='blind' else query[i:i+1]*0
                gamma,beta=self.film(q).chunk(2,-1)
                h=h*(1+.1*gamma[:,:,None])+beta[:,:,None]
                logits=self.density(h)
                logits=F.interpolate(logits.float(),size=length,mode='linear',align_corners=False).squeeze(1)
                p=logits.clamp(-12,12).softmax(-1)
            p=(1-self.floor)*p.float()+self.floor/length
            parts.append(F.pad(p,(0,x.shape[1]-length)))
        return torch.cat(parts,0)

    def forward(self,x,lengths,dt,query,mask=None,intervention=None):
        p=self.distribution(x,lengths,query)
        grid=inverse_cdf(p,self.tokens,lengths)
        if intervention=='uniform':
            grid=((torch.arange(self.tokens,device=x.device)+.5)/self.tokens).expand(len(x),-1)
        values=sample_linear(x/1000.,grid,lengths)
        if intervention in ('zero','coordinate'):values=values*0
        elif intervention=='permutation':
            permutation=torch.randperm(self.tokens,generator=torch.Generator().manual_seed(31415)).to(values.device)
            values=values[:,permutation]
        elif intervention=='cross':values=values.roll(1,0)
        elif intervention=='query':values,grid=values*0,grid*0
        observed=sample_linear(mask[:,:,None].float(),grid,lengths).squeeze(-1) if mask is not None else None
        if intervention=='query':
            # 严格Query-only答案头不接收窗口长度、掩码变化或任何数据相关坐标。
            lengths=torch.ones_like(lengths);dt=torch.ones_like(dt);observed=torch.ones_like(grid)
        output=self.readout(values,grid,lengths,dt,query,observed)
        return dict(output=output,p=p,grid=grid,values=values)
