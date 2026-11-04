"""补充预算诊断：已知全部候选窗口的查询盲 Oracle，不改动冻结主矩阵。"""
import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch
from torch.nn import functional as F

from model import gaussian_smooth, sample_linear
from phase2_data import DIFFICULTIES, DataConfig, PairedGenerator, paired_inputs
from phase2_experiment import source_metadata, write_json
from phase2_model import Phase2QA


def forward(model, data, config, sigma=0.):
    """所有查询共用同一网格；按时间排序窗口，避免暴露类别插入顺序。"""
    x, query, labels = paired_inputs(data)
    starts = data["starts"].sort(-1).values
    fraction = (torch.arange(model.sampler.tokens // 4, device=x.device) + .5) / (model.sampler.tokens // 4)
    grid = ((starts[:, :, None] + fraction * (config.event_width - 1)) / (config.length - 1)).reshape(starts.shape[0], -1)
    grid = grid.repeat_interleave(4, 0)
    values = sample_linear(gaussian_smooth(x, sigma), grid)
    return model.readout(values, query), grid, labels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("results"))
    args = parser.parse_args()
    torch.set_num_threads(4)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    root = args.root
    output = root / "budget-probes"
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"禁止覆盖已有预算诊断：{output}")
    output.mkdir(exist_ok=True)
    config = DataConfig()
    specification = {"tokens": [32, 64, 512], "seeds": [7, 11, 23], "steps": 600,
                     "data": config.dictionary(), "source": source_metadata(),
                     "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                     "status": "查看主矩阵结果后增加的预算诊断；未修改数据、测试集或主模型",
                     "purpose": "验证查询盲的理想候选覆盖是否已足够，避免把少 Token 等同于信息瓶颈"}
    write_json(output / "specification.json", specification)
    # 直接使用已完成主矩阵的输入哈希，避免依赖尚未生成的汇总文件。
    reference = json.loads((root / "main/adaptive-t512-c256-s7/metrics.json").read_text())
    fingerprints = {level: row["evaluation_sha256"] for level, row in reference.items()}
    for tokens in (32, 64, 512):
        for seed in (7, 11, 23):
            directory = output / f"blind-oracle-t{tokens}-s{seed}"
            if directory.exists():
                raise FileExistsError(directory)
            directory.mkdir()
            torch.manual_seed(seed)
            model = Phase2QA(tokens=tokens, event_width=config.event_width, method="uniform").to(device)
            optimizer = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=1e-4)
            generator = PairedGenerator(config, seed + 100000, device)
            trace = []
            for step in range(1, 601):
                data = generator.batch(8)
                sigma = 32 * max(0., 1 - (step - 1) / 360)
                optimizer.zero_grad(set_to_none=True)
                logits, _, labels = forward(model, data, config, sigma)
                loss = F.binary_cross_entropy_with_logits(logits, labels)
                loss.backward()
                norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 5.)
                optimizer.step()
                trace.append({"step": step, "loss": loss.item(), "gradient": norm.item(), "sigma": sigma})
            metrics, snapshots = {}, {}
            model.eval()
            with torch.no_grad():
                for level, name in enumerate(DIFFICULTIES):
                    generator = PairedGenerator(config, 424242 + level * 10000, device)
                    fingerprint = hashlib.sha256()
                    correct = torch.zeros(4, device=device)
                    for batch_index in range(16):
                        data = generator.batch(8, level)
                        logits, grid, labels = forward(model, data, config)
                        correct += ((logits >= 0) == labels.bool()).reshape(8, 4).sum(0)
                        fingerprint.update(data["x"].cpu().numpy().tobytes())
                        fingerprint.update(data["labels"].cpu().numpy().tobytes())
                        if batch_index == 0:
                            snapshots[name] = {"grid": grid[:4].cpu().tolist(), "starts": data["starts"][0].tolist(),
                                               "labels": data["labels"][0].int().tolist()}
                    assert fingerprint.hexdigest() == fingerprints[name]
                    metrics[name] = {"accuracy": (correct.sum() / 512).item(), "per_class_accuracy": (correct / 128).cpu().tolist(),
                                     "target_hit": 1., "target_four_points": 1., "target_occupancy": .25,
                                     "query_selectivity": 0., "evaluation_sha256": fingerprint.hexdigest()}
            write_json(directory / "config.json", {**specification, "tokens": tokens, "seed": seed})
            write_json(directory / "trace.json", trace)
            write_json(directory / "metrics.json", metrics)
            write_json(directory / "snapshots.json", snapshots)
            fig, ax = plt.subplots(figsize=(8, 3), constrained_layout=True)
            ax.plot([x["step"] for x in trace], [x["loss"] for x in trace], lw=.7)
            ax.set(xlabel="Update", ylabel="QA BCE", title=f"Query-blind candidate oracle; {tokens} tokens; seed {seed}")
            fig.savefig(directory / "training.png", dpi=120)
            plt.close(fig)
            print(json.dumps({"completed": directory.name, "metrics": metrics}), flush=True)


if __name__ == "__main__":
    main()
