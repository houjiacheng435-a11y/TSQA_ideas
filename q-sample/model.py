"""Query-conditioned inverse-CDF sampling; no event labels enter the model."""
import math

import torch
from torch import nn
from torch.nn import functional as F


def inverse_cdf(mass, count):
    """Midpoint quantiles of positive, piecewise-constant bins on [0, 1].

    Search indices are discrete; interpolation is differentiable almost
    everywhere. FP64 prevents a small density floor vanishing in the CDF.
    """
    if mass.ndim != 2 or mass.shape[1] < 1 or count < 1:
        raise ValueError("Expected [batch, bins] masses and count >= 1")
    if not bool(torch.isfinite(mass).all()) or not bool((mass > 0).all()):
        raise ValueError("Masses must be finite and strictly positive")
    p = mass.double()
    p = p / p.sum(-1, keepdim=True)
    cdf = F.pad(p.cumsum(-1), (1, 0))
    cdf = cdf / cdf[:, -1:]
    u = (torch.arange(count, device=mass.device, dtype=p.dtype) + 0.5) / count
    u = u.expand(mass.shape[0], -1).contiguous()
    index = torch.searchsorted(cdf.contiguous(), u, right=True) - 1
    index = index.clamp(0, mass.shape[1] - 1)
    lo, hi = cdf.gather(1, index), cdf.gather(1, index + 1)
    fraction = (u - lo) / (hi - lo).clamp_min(torch.finfo(p.dtype).eps)
    grid = (index + fraction) / mass.shape[1]
    return grid.to(mass.dtype)


def sample_linear(x, grid):
    """x: [B,L,C], grid: [B,N] in [0,1]; coordinate and value gradients."""
    positions = grid.clamp(0, 1) * (x.shape[1] - 1)
    left = positions.floor().long()
    right = (left + 1).clamp_max(x.shape[1] - 1)
    a = x.gather(1, left[..., None].expand(-1, -1, x.shape[-1]))
    b = x.gather(1, right[..., None].expand(-1, -1, x.shape[-1]))
    return torch.lerp(a, b, (positions - left)[..., None])


def gaussian_smooth(x, sigma):
    """Finite, normalized Gaussian via FFT convolution and replicated edges."""
    if sigma <= 0:
        return x
    radius = max(1, math.ceil(3 * sigma))
    t = torch.arange(-radius, radius + 1, device=x.device, dtype=x.dtype)
    kernel = torch.exp(-0.5 * (t / sigma).square())
    kernel = kernel / kernel.sum()
    padded = F.pad(x.transpose(1, 2), (radius, radius), mode="replicate")
    fft_size = 1 << (padded.shape[-1] + kernel.numel() - 2).bit_length()
    result = torch.fft.irfft(
        torch.fft.rfft(padded, n=fft_size)
        * torch.fft.rfft(kernel, n=fft_size), n=fft_size)
    start = kernel.numel() - 1
    return result[..., start:start + x.shape[1]].transpose(1, 2)


class QSample(nn.Module):
    def __init__(self, channels=1, coarse=256, tokens=512, width=48,
                 epsilon=1e-4, statistics=True):
        super().__init__()
        if coarse < 1 or tokens < 1 or not 0 < epsilon <= 1:
            raise ValueError("Invalid bin count, token budget or density floor")
        self.coarse, self.tokens = coarse, tokens
        self.epsilon, self.statistics = epsilon, statistics
        self.encoder = nn.Sequential(
            nn.Conv1d(channels * (5 if statistics else 1), width, 3, padding=1),
            nn.GELU(), nn.Conv1d(width, width, 3, padding=1), nn.GELU())
        self.query = nn.Linear(1, width * 2)
        self.density = nn.Conv1d(width, 1, 1)
        # Start with an almost uniform grid, retaining query/feature gradients.
        nn.init.normal_(self.density.weight, std=0.001)
        nn.init.zeros_(self.density.bias)

    def coarse_features(self, x):
        z = x.transpose(1, 2)
        mean = F.adaptive_avg_pool1d(z, self.coarse)
        if not self.statistics:
            return mean
        var = (F.adaptive_avg_pool1d(z.square(), self.coarse) - mean.square())
        maximum = F.adaptive_max_pool1d(z, self.coarse)
        minimum = -F.adaptive_max_pool1d(-z, self.coarse)
        difference = F.pad(z.diff(dim=-1).abs(), (1, 0))
        difference = F.adaptive_max_pool1d(difference, self.coarse)
        return torch.cat((mean, var.clamp_min(0), minimum, maximum, difference), 1)

    def forward(self, x, query, mode="adaptive", sigma=0):
        features = self.encoder(self.coarse_features(x))
        scale, shift = self.query(query).chunk(2, -1)
        mixed = F.gelu(features * (1 + scale[..., None]) + shift[..., None])
        coarse_mass = self.density(mixed).squeeze(1).softmax(-1)
        if mode == "uniform":
            mass = torch.ones_like(coarse_mass) / self.coarse
        elif mode == "adaptive":
            mass = (1 - self.epsilon) * coarse_mass + self.epsilon / self.coarse
        else:
            raise ValueError(f"Unknown mode: {mode}")
        # Interpolation changes the total; normalize again on the dense axis.
        dense_mass = F.interpolate(mass[:, None], size=x.shape[1],
                                   mode="linear", align_corners=False).squeeze(1)
        dense_mass = dense_mass / dense_mass.sum(-1, keepdim=True)
        grid = inverse_cdf(dense_mass, self.tokens)
        sampled = sample_linear(gaussian_smooth(x, sigma), grid)
        return {"values": sampled, "grid": grid, "mass": dense_mass,
                "coarse_mass": mass}


class TimeProjection(nn.Module):
    """Continuous Fourier time features plus explicit coordinate and gap.

    Fourier features are not RoPE. Physical duration must also be provided to
    a future QA backend when sequences have different sampling rates/lengths.
    """
    def __init__(self, channels=1, width=48, frequencies=8):
        super().__init__()
        self.register_buffer("frequencies", 2 ** torch.arange(frequencies).float())
        self.project = nn.Sequential(nn.Linear(channels + 2 + 2 * frequencies, width),
                                     nn.GELU(), nn.Linear(width, width), nn.GELU())

    def forward(self, values, grid):
        phase = 2 * math.pi * grid[..., None] * self.frequencies
        gaps = F.pad(grid.diff(dim=-1), (1, 0))
        return self.project(torch.cat((values, grid[..., None], gaps[..., None],
                                       phase.sin(), phase.cos()), -1))


class SyntheticQA(nn.Module):
    def __init__(self, readout="signal", **kwargs):
        super().__init__()
        if readout not in ("signal", "signal_time", "signal_time_detached"):
            raise ValueError(readout)
        self.readout = readout
        self.sampler = QSample(**kwargs)
        width = kwargs.get("width", 48)
        self.projection = (nn.Sequential(nn.Linear(1, width), nn.GELU(),
                                         nn.Linear(width, width), nn.GELU())
                           if readout == "signal" else TimeProjection(width=width))
        self.head = nn.Sequential(nn.Linear(width * 2, width), nn.GELU(),
                                  nn.Linear(width, 1))

    def forward(self, x, query, mode="adaptive", sigma=0, value_mode="normal"):
        density_query = torch.zeros_like(query) if mode == "adaptive_query_blind" else query
        sampler_mode = "adaptive" if mode == "adaptive_query_blind" else mode
        result = self.sampler(x, density_query, mode=sampler_mode, sigma=sigma)
        # Sign-normalize the requested event. The head never sees coarse features.
        values = result["values"] * query[:, None, :]
        if value_mode == "zero":
            values = torch.zeros_like(values)
        elif value_mode != "normal":
            raise ValueError(value_mode)
        if self.readout == "signal":
            tokens = self.projection(values)
        else:
            grid = result["grid"].detach() if self.readout == "signal_time_detached" else result["grid"]
            tokens = self.projection(values, grid)
        pooled = torch.cat((tokens.mean(1), tokens.amax(1)), -1)
        result["logits"] = self.head(pooled).squeeze(-1)
        return result
