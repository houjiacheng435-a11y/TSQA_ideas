"""仅作诊断：直接读取粗特征的分类器，禁止与 Signal-Only 主模型混报。"""
import argparse
import hashlib
import json
from pathlib import Path

import torch
from torch import nn
from torch.nn import functional as F

from model import QSample
from phase2_data import CLASSES, DIFFICULTIES, DataConfig, PairedGenerator, paired_inputs
from phase2_experiment import source_metadata, write_json


class EncoderProbe(nn.Module):
    """检测现有粗特征是否足以分类，不经过采样，也不检验证据选择。"""
    def __init__(self, coarse):
        super().__init__()
        self.sampler = QSample(coarse=coarse, width=48, query_dim=len(CLASSES))
        self.head = nn.Sequential(nn.Linear(96, 48), nn.GELU(), nn.Linear(48, 1))

    def forward(self, x, query):
        hidden = self.sampler.encoder(self.sampler.coarse_features(x))
        scale, shift = self.sampler.query(query).chunk(2, -1)
        hidden = F.gelu(hidden * (1 + scale[..., None]) + shift[..., None])
        return self.head(torch.cat((hidden.mean(-1), hidden.amax(-1)), -1)).squeeze(-1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("results"))
    args = parser.parse_args()
    torch.set_num_threads(4)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    output = args.root / "probes"
    output.mkdir(parents=True, exist_ok=True)
    data_config = DataConfig()
    for coarse in (256, 1024):
        for seed in (7, 11, 23):
            name = f"encoder-probe-c{coarse}-s{seed}"
            directory = output / name
            if directory.exists():
                raise FileExistsError(directory)
            directory.mkdir()
            torch.manual_seed(seed)
            model = EncoderProbe(coarse).to(device)
            optimizer = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=1e-4)
            train = PairedGenerator(data_config, seed + 100000, device)
            trace = []
            for step in range(1, 601):
                x, query, labels = paired_inputs(train.batch(8))
                optimizer.zero_grad(set_to_none=True)
                loss = F.binary_cross_entropy_with_logits(model(x, query), labels)
                loss.backward()
                norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 5.)
                optimizer.step()
                trace.append({"step": step, "loss": loss.item(), "gradient": norm.item()})
            metrics = {}
            model.eval()
            with torch.no_grad():
                for level, difficulty in enumerate(DIFFICULTIES):
                    test = PairedGenerator(data_config, 424242 + level * 10000, device)
                    correct = torch.zeros(4, device=device)
                    for _ in range(16):
                        x, query, labels = paired_inputs(test.batch(8, level))
                        correct += ((model(x, query) >= 0) == labels.bool()).reshape(8, 4).sum(0)
                    metrics[difficulty] = {"accuracy": (correct.sum() / 512).item(),
                                           "per_class_accuracy": (correct / 128).cpu().tolist()}
            write_json(directory / "config.json", {"coarse": coarse, "seed": seed, "steps": 600,
                                                    "data": data_config.dictionary(), "source": source_metadata(),
                                                    "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                                    "purpose": "粗特征可辨识性诊断；直接旁路采样，非主实验"})
            write_json(directory / "trace.json", trace)
            write_json(directory / "metrics.json", metrics)
            print(json.dumps({"completed": name, "metrics": metrics}), flush=True)


if __name__ == "__main__":
    main()
