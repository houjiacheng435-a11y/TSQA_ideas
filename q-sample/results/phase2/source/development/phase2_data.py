"""多形态、配对查询合成数据；事件坐标仅用于诊断和 Oracle 对照。"""
from dataclasses import asdict, dataclass

import numpy as np
import torch


CLASSES = ("positive_square", "negative_square", "oscillation", "double_pulse")
DIFFICULTIES = ("none", "few", "strong")
VERSION = "phase2-matched-histogram-v1"


@dataclass
class DataConfig:
    length: int = 100000
    event_width: int = 384
    noise: float = 0.06
    target_amplitude_low: float = 0.8
    target_amplitude_high: float = 1.2

    def __post_init__(self):
        if self.event_width < 64 or self.length < 64 * self.event_width:
            raise ValueError("事件宽度至少为 64，序列长度至少为事件宽度的 64 倍")

    def dictionary(self):
        return {**asdict(self), "classes": CLASSES, "version": VERSION}


def templates(width):
    """四类完整事件模板；双脉冲的单个窄瓣不属于宽单方波类。"""
    t = (np.arange(width) + .5) / width
    positive = ((t >= .15) & (t < .85)).astype(np.float32)
    negative = -positive
    oscillation = (np.sin(6 * np.pi * t) * np.sin(np.pi * t) ** 2).astype(np.float32)
    double = (((t >= .12) & (t < .28)) | ((t >= .72) & (t < .88))).astype(np.float32)
    return np.stack((positive, negative, oscillation, double))


class PairedGenerator:
    def __init__(self, config, seed, device="cpu"):
        self.config, self.device = config, device
        self.rng = np.random.default_rng(seed)
        self.torch_rng = torch.Generator(device=device).manual_seed(seed + 101)
        self.shapes = templates(config.event_width)

    def _locations(self, count):
        """在全时间轴均匀提议位置，拒绝重叠及过近事件。"""
        c = self.config
        starts = []
        for _ in range(count):
            for attempt in range(10000):
                start = int(self.rng.integers(c.event_width, c.length - 2 * c.event_width))
                if all(abs(start - old) >= c.event_width * 1.5 for old in starts):
                    starts.append(start)
                    break
            else:
                raise RuntimeError("无法生成非重叠事件位置")
        return starts

    def batch(self, size, difficulty=None, labels_override=None):
        if size % 2:
            raise ValueError("配对平衡批次的序列数必须为偶数")
        c, rng = self.config, self.rng
        labels = rng.integers(0, 2, (size // 2, len(CLASSES)))
        labels = np.concatenate((labels, 1 - labels), axis=0)
        rng.shuffle(labels)
        if labels_override is not None:
            labels = np.asarray(labels_override, dtype=np.int64)
            if labels.shape != (size, len(CLASSES)):
                raise ValueError("标签形状不匹配")
        levels = rng.integers(0, 3, size) if difficulty is None else np.full(size, difficulty)
        x = torch.randn(size, c.length, 1, generator=self.torch_rng, device=self.device) * c.noise
        starts = np.zeros((size, len(CLASSES)), dtype=np.int64)
        all_starts, extra_counts, payloads, amplitudes = [], [], [], []
        for row in range(size):
            level = levels[row]
            count = 0 if level == 0 else int(rng.integers(2, 6) if level == 1 else rng.integers(12, 21))
            locations = self._locations(len(CLASSES) + count)
            starts[row] = locations[:len(CLASSES)]
            all_starts.append(locations)
            extra_counts.append(count)
            row_payloads, row_amplitudes = [], []
            for category in range(len(CLASSES)):
                amplitude = float(rng.uniform(c.target_amplitude_low, c.target_amplitude_high))
                # 每次都消耗相同随机数；反事实标签替换不改变位置、幅值和干扰。
                permutation = rng.permutation(c.event_width)
                waveform = self.shapes[category]
                waveform = waveform if labels[row, category] else waveform[permutation]
                row_payloads.append((waveform * amplitude).astype(np.float32))
                row_amplitudes.append(amplitude)
            for _ in range(count):
                t = (np.arange(c.event_width) + .5) / c.event_width
                kind = int(rng.integers(0, 3))
                if kind == 0:
                    waveform = (1 - abs(2 * t - 1)) * rng.choice([-1, 1])
                elif kind == 1:
                    waveform = 2 * ((t * 5) % 1) - 1
                else:
                    waveform = np.sin(2 * np.pi * (t + 8 * t ** 2))
                amplitude = float(rng.uniform(2., 6.) if level == 2 else rng.uniform(.8, 2.))
                row_payloads.append((waveform * amplitude).astype(np.float32))
                row_amplitudes.append(amplitude)
            payload = torch.from_numpy(np.stack(row_payloads)).to(self.device)
            positions = torch.tensor(locations, device=self.device)[:, None] + torch.arange(c.event_width, device=self.device)[None]
            x[row, positions, 0] += payload
            payloads.append(row_payloads)
            amplitudes.append(row_amplitudes)
        return {
            "x": x, "labels": torch.tensor(labels, device=self.device).float(),
            "starts": torch.tensor(starts, device=self.device),
            "all_starts": all_starts, "extra_counts": extra_counts,
            "difficulty": levels.tolist(), "payloads": payloads, "amplitudes": amplitudes,
        }


def paired_inputs(data):
    """同一原始序列扩展为四个查询，查询和标签按序列优先排列。"""
    x = data["x"]
    query = torch.eye(len(CLASSES), device=x.device).repeat(x.shape[0], 1)
    return x.repeat_interleave(len(CLASSES), 0), query, data["labels"].flatten()
