"""复用第一阶段采样原语；主答案头仅接收真实采样值与类别查询。"""
import torch
from torch import nn
from torch.nn import functional as F

from model import QSample, TimeProjection, gaussian_smooth, inverse_cdf, sample_linear
from phase2_data import CLASSES


METHODS = ("adaptive", "query_blind", "uniform", "uniform_blur", "saliency", "no_blur", "oracle", "signal_time")


class EvidenceReadout(nn.Module):
    """卷积只识别采样值的有序形态，不接收密度、原始坐标或全局特征。"""
    def __init__(self, width, with_time=False):
        super().__init__()
        self.with_time = with_time
        self.time = TimeProjection(width=width) if with_time else None
        self.input = nn.Conv1d(width if with_time else 1, width, 5, padding=2)
        self.conv = nn.Sequential(nn.GELU(), nn.Conv1d(width, width, 3, padding=1), nn.GELU())
        self.query = nn.Linear(len(CLASSES), width * 2)
        self.head = nn.Sequential(nn.Linear(width * 2, width), nn.GELU(), nn.Linear(width, 1))

    def forward(self, values, query, grid=None):
        if self.with_time:
            values = self.time(values, grid)
        hidden = self.input(values.transpose(1, 2))
        scale, shift = self.query(query).chunk(2, -1)
        hidden = self.conv(hidden * (1 + scale[..., None]) + shift[..., None])
        return self.head(torch.cat((hidden.mean(-1), hidden.amax(-1)), -1)).squeeze(-1)


class Phase2QA(nn.Module):
    def __init__(self, tokens=64, coarse=256, width=48, method="adaptive", event_width=384):
        super().__init__()
        if method not in METHODS:
            raise ValueError(method)
        self.method, self.event_width = method, event_width
        self.sampler = QSample(tokens=tokens, coarse=coarse, width=width, query_dim=len(CLASSES))
        self.readout = EvidenceReadout(width, with_time=method == "signal_time")

    def forward(self, x, query, sigma=0., oracle_starts=None):
        method = self.method
        if method in ("adaptive", "query_blind", "no_blur", "signal_time"):
            sampler_query = torch.zeros_like(query) if method == "query_blind" else query
            result = self.sampler(x, sampler_query, sigma=sigma)
        else:
            if method == "saliency":
                features = self.sampler.coarse_features(x)
                score = features[:, 1] + features[:, 2:4].abs().amax(1) + features[:, 4]
                mass = score.clamp_min(0) + 1e-4
                mass = mass / mass.sum(-1, keepdim=True)
            else:
                mass = x.new_full((x.shape[0], self.sampler.coarse), 1 / self.sampler.coarse)
            dense = F.interpolate(mass[:, None], size=x.shape[1], mode="linear", align_corners=False).squeeze(1)
            dense = dense / dense.sum(-1, keepdim=True)
            if method == "oracle":
                if oracle_starts is None:
                    raise ValueError("仅 Oracle 对照需要事件窗口位置")
                fraction = (torch.arange(self.sampler.tokens, device=x.device, dtype=x.dtype) + .5) / self.sampler.tokens
                grid = (oracle_starts[:, None] + fraction * (self.event_width - 1)) / (x.shape[1] - 1)
                # Oracle 的可视化概率质量只覆盖对应候选窗口，不依赖存在性标签。
                index = torch.arange(x.shape[1], device=x.device)[None]
                dense = ((index >= oracle_starts[:, None]) & (index < oracle_starts[:, None] + self.event_width)).to(x.dtype)
                dense = dense / dense.sum(-1, keepdim=True)
                mass = F.adaptive_avg_pool1d(dense[:, None], self.sampler.coarse).squeeze(1)
                mass = mass / mass.sum(-1, keepdim=True)
            else:
                grid = inverse_cdf(dense, self.sampler.tokens)
            result = {"values": sample_linear(gaussian_smooth(x, sigma), grid), "grid": grid,
                      "mass": dense, "coarse_mass": mass}
        result["logits"] = self.readout(result["values"], query,
                                        result["grid"] if self.readout.with_time else None)
        return result

    def intervene(self, result, query, kind, raw=None):
        """诊断干预只改变答案头输入，不重新训练采样器。"""
        values, grid = result["values"], result["grid"]
        if kind == "zero":
            values = torch.zeros_like(values)
        elif kind == "uniform":
            fraction = (torch.arange(grid.shape[1], device=grid.device, dtype=grid.dtype) + .5) / grid.shape[1]
            grid = fraction.expand_as(grid)
            values = sample_linear(raw, grid)
        elif kind == "reverse":
            values = values.flip(1)
        else:
            raise ValueError(kind)
        return self.readout(values, query, grid if self.readout.with_time else None)
