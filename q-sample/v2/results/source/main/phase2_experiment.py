"""第二阶段训练、配对评估与干预；主实验仅由答案 BCE 优化。"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from torch.nn import functional as F

from model import sample_linear
from phase2_data import CLASSES, DIFFICULTIES, DataConfig, PairedGenerator, paired_inputs
from phase2_model import METHODS, Phase2QA


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def source_metadata():
    root = Path(__file__).parent
    names = ("model.py", "phase2_data.py", "phase2_model.py", "phase2_experiment.py")
    return {"sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names},
            "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
            "torch": torch.__version__, "numpy": np.__version__}


def region_allocation(result, data, config):
    """按完整事件窗口统计位置覆盖；密度质量与采样点占比单独计算。"""
    size, classes = data["labels"].shape
    grid = result["grid"].reshape(size, classes, -1)
    positions = grid * (config.length - 1)
    starts = data["starts"]
    inside = ((positions[:, :, None] >= starts[:, None, :, None])
              & (positions[:, :, None] <= starts[:, None, :, None] + config.event_width - 1))
    counts = inside.sum(-1)
    occupancy = inside.float().mean(-1)
    dense = result["mass"].reshape(size, classes, config.length)
    cdf = F.pad(dense.double().cumsum(-1), (1, 0))
    lower = starts[:, None, :].expand(-1, classes, -1)
    mass = cdf.gather(2, lower + config.event_width) - cdf.gather(2, lower)
    extra_occ = torch.zeros(size, classes, device=grid.device)
    extra_mass = torch.zeros_like(extra_occ)
    for row, locations in enumerate(data["all_starts"]):
        if len(locations) > classes:
            locations = torch.tensor(locations[classes:], device=grid.device)
            extra_inside = ((positions[row, :, None] >= locations[None, :, None])
                            & (positions[row, :, None] <= locations[None, :, None] + config.event_width - 1))
            extra_occ[row] = extra_inside.any(1).float().mean(-1)
            lower = locations[None].expand(classes, -1)
            extra_mass[row] = (cdf[row].gather(1, lower + config.event_width) - cdf[row].gather(1, lower)).sum(-1)
    return occupancy, counts, mass, extra_occ, extra_mass, inside


@torch.no_grad()
def evaluate(model, args, level, snapshot=False):
    model.eval()
    generator = PairedGenerator(args.data, args.eval_seed + 10000 * level, args.device)
    sums = {}
    total = positive_count = sequence_count = paired_count = 0
    class_correct = torch.zeros(len(CLASSES), device=args.device)
    class_total = 0
    fingerprint = hashlib.sha256()
    saved = None
    class_counts = np.zeros((len(CLASSES), 2), dtype=np.int64)
    example_records = []
    for offset in range(0, args.eval_sequences, args.batch_size):
        size = min(args.batch_size, args.eval_sequences - offset)
        data = generator.batch(size, level)
        x, query, labels = paired_inputs(data)
        fingerprint.update(data["x"].cpu().numpy().tobytes())
        fingerprint.update(data["labels"].cpu().numpy().tobytes())
        starts = data["starts"].flatten()
        result = model(x, query, oracle_starts=starts if model.method == "oracle" else None)
        logits = result["logits"]
        predicted = logits >= 0
        correct = predicted == labels.bool()
        zero = model.intervene(result, query, "zero")
        uniform = model.intervene(result, query, "uniform", raw=x)
        grid3 = result["grid"].reshape(size, len(CLASSES), -1)
        other_grid = grid3.roll(1, 1).reshape_as(result["grid"])
        other_values = sample_linear(x, other_grid)
        other_logits = model.readout(other_values, query, other_grid if model.readout.with_time else None)
        shuffle_rng = torch.Generator(device=args.device).manual_seed(7721)
        permutation = torch.randperm(result["values"].shape[1], device=args.device, generator=shuffle_rng)
        shuffled = model.readout(result["values"][:, permutation], query,
                                 result["grid"] if model.readout.with_time else None)
        occupancy, counts, mass, extra_occ, extra_mass, inside = region_allocation(result, data, args.data)
        target_occ = occupancy.diagonal(dim1=1, dim2=2)
        target_mass = mass.diagonal(dim1=1, dim2=2)
        target_counts = counts.diagonal(dim1=1, dim2=2)
        mask = data["labels"].bool()
        removed = result["values"].clone()
        own_inside = inside[:, torch.arange(len(CLASSES)), torch.arange(len(CLASSES))].reshape_as(result["grid"])
        removed[own_inside] = 0
        removed_logits = model.readout(removed, query, result["grid"] if model.readout.with_time else None)
        wrong_target_occ = (occupancy.sum(1) - target_occ) / (len(CLASSES) - 1)
        wrong_target_mass = (mass.sum(1) - target_mass) / (len(CLASSES) - 1)
        distractor_occ = occupancy.sum(-1) - target_occ + extra_occ
        distractor_mass = mass.sum(-1) - target_mass + extra_mass

        def add(name, value):
            sums[name] = sums.get(name, 0.) + float(value)

        add("loss", F.binary_cross_entropy_with_logits(logits, labels, reduction="sum").item())
        add("accuracy", correct.sum().item())
        for key, prediction in (("zero_signal_accuracy", zero), ("uniform_grid_accuracy", uniform),
                                ("wrong_query_grid_accuracy", other_logits), ("shuffled_values_accuracy", shuffled)):
            add(key, ((prediction >= 0) == labels.bool()).sum().item())
        add("positive_recall", predicted.reshape_as(mask)[mask].sum().item())
        add("removed_target_yes_rate", (removed_logits.reshape_as(mask)[mask] >= 0).sum().item())
        for key, values in (("target_hit", target_counts > 0), ("target_four_points", target_counts >= 4),
                            ("target_occupancy", target_occ), ("target_mass", target_mass),
                            ("distractor_occupancy", distractor_occ), ("distractor_mass", distractor_mass),
                            ("extra_distractor_occupancy", extra_occ),
                            ("query_selectivity", target_occ - wrong_target_occ),
                            ("query_mass_selectivity", target_mass - wrong_target_mass)):
            add(key, values[mask].sum().item())
        add("all_queries_correct", correct.reshape(size, -1).all(-1).sum().item())
        for row in range(size):
            present = mask[row].nonzero().flatten().tolist()
            for i in present:
                for j in present:
                    if j <= i:
                        continue
                    transfer = occupancy[row, i, i] + occupancy[row, j, j] - occupancy[row, j, i] - occupancy[row, i, j]
                    add("paired_transfer", transfer.item() / 2)
                    add("paired_transfer_direction", (transfer > 1e-8).item())
                    paired_count += 1
            example_records.append({"sequence": offset + row,
                                    "labels": data["labels"][row].int().tolist(),
                                    "probabilities": logits.sigmoid().reshape(size, -1)[row].cpu().tolist(),
                                    "target_counts": target_counts[row].tolist(),
                                    "target_occupancy": target_occ[row].tolist(),
                                    "occupancy_matrix": occupancy[row].cpu().tolist(),
                                    "extra_count": data["extra_counts"][row]})
        class_correct += correct.reshape(size, -1).sum(0)
        class_total += size
        class_counts[:, 1] += data["labels"].sum(0).cpu().numpy().astype(np.int64)
        class_counts[:, 0] += size - data["labels"].sum(0).cpu().numpy().astype(np.int64)
        total += labels.numel()
        sequence_count += size
        positive_count += mask.sum().item()
        if snapshot and saved is None:
            # 固定选择测试流第一条信号，避免按模型表现挑图。
            saved = {"signal": data["x"][0, ::max(1, args.data.length // 12500), 0].cpu().tolist(),
                     "labels": data["labels"][0].int().tolist(), "starts": data["starts"][0].tolist(),
                     "all_starts": data["all_starts"][0],
                     "probabilities": logits.sigmoid().reshape(size, -1)[0].cpu().tolist(),
                     "coarse_mass": result["coarse_mass"].reshape(size, len(CLASSES), -1)[0].cpu().tolist(),
                     "grid": grid3[0].cpu().tolist(), "occupancy_matrix": occupancy[0].cpu().tolist()}
    all_denominator = {"loss", "accuracy", "zero_signal_accuracy", "uniform_grid_accuracy", "wrong_query_grid_accuracy", "shuffled_values_accuracy"}
    for key in sums:
        denominator = total if key in all_denominator else sequence_count if key == "all_queries_correct" else paired_count if key.startswith("paired_transfer") else positive_count
        sums[key] /= max(1, denominator)
    sums.update(examples=total, sequences=sequence_count, positive_examples=positive_count,
                paired_present_pairs=paired_count, per_class_accuracy=(class_correct / class_total).cpu().tolist(),
                class_label_counts=class_counts.tolist(), prior_baseline=.5, evaluation_sha256=fingerprint.hexdigest())
    model.train()
    return sums, saved, example_records


def plot_outputs(directory, args, trace, snapshots):
    fig, ax = plt.subplots(2, 1, figsize=(10, 6), constrained_layout=True)
    ax[0].plot([x["step"] for x in trace], [x["loss"] for x in trace], lw=.7)
    ax[0].set(ylabel="QA BCE", xlabel="Update")
    ax[1].semilogy([x["step"] for x in trace], [max(x["density_gradient"], 1e-12) for x in trace], lw=.7)
    ax[1].set(ylabel="Density gradient norm", xlabel="Update")
    fig.savefig(directory / "training.png", dpi=140)
    plt.close(fig)
    for level, snapshot in snapshots.items():
        fig, axes = plt.subplots(5, 1, figsize=(13, 12), constrained_layout=True)
        axes[0].plot(np.linspace(0, 1, len(snapshot["signal"])), snapshot["signal"], lw=.5)
        axes[0].set(ylabel="Raw signal", title=f"{args.method}, {args.tokens} tokens, {level}; first sequence")
        for category, name in enumerate(CLASSES):
            ax = axes[category + 1]
            density = snapshot["coarse_mass"][category]
            ax.plot((np.arange(len(density)) + .5) / len(density), density, lw=.9)
            ax.set(ylabel=f"Q{category} mass", title=f"{name}: y={snapshot['labels'][category]}, p={snapshot['probabilities'][category]:.3f}")
            grid = snapshot["grid"][category]
            ax.vlines(grid, 0, max(density) * .15 + 1e-6, color="black", lw=.5, alpha=.4)
            for other, start in enumerate(snapshot["starts"]):
                color = "green" if other == category and snapshot["labels"][other] else "orange"
                ax.axvspan(start / args.data.length, (start + args.data.event_width) / args.data.length, color=color, alpha=.25)
            ax.set_xlim(0, 1)
        axes[-1].set_xlabel("Normalized original time; ticks = sample coordinates")
        fig.savefig(directory / f"queries-{level}.png", dpi=130)
        plt.close(fig)


def train_run(args):
    directory = args.output / f"{args.method}-t{args.tokens}-c{args.coarse}-s{args.seed}"
    if directory.exists():
        raise FileExistsError(f"禁止覆盖已有实验：{directory}")
    directory.mkdir(parents=True)
    torch.manual_seed(args.seed)
    model = Phase2QA(tokens=args.tokens, coarse=args.coarse, width=args.width, method=args.method,
                     event_width=args.data.event_width).to(args.device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    config = {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items() if k != "data"}
    config.update(data=args.data.dictionary(), source=source_metadata(),
                  supervision="仅 QA BCE；Oracle 对照独立使用候选事件窗口，主模型不接收元数据",
                  readout="signal_time" if args.method == "signal_time" else "signal_only",
                  gpu=torch.cuda.get_device_name() if args.device.startswith("cuda") else None)
    write_json(directory / "config.json", config)
    generator = PairedGenerator(args.data, args.seed + args.train_seed_offset, args.device)
    trace = []
    start_time = time.monotonic()
    for step in range(1, args.steps + 1):
        data = generator.batch(args.batch_size)
        x, query, labels = paired_inputs(data)
        sigma = args.sigma * max(0., 1 - (step - 1) / max(1, args.steps * args.anneal_fraction))
        if args.method in ("uniform", "no_blur"):
            sigma = 0.
        optimizer.zero_grad(set_to_none=True)
        starts = data["starts"].flatten() if args.method == "oracle" else None
        result = model(x, query, sigma=sigma, oracle_starts=starts)
        loss = F.binary_cross_entropy_with_logits(result["logits"], labels)
        if not torch.isfinite(loss):
            write_json(directory / "failure.json", {"step": step, "reason": "非有限损失", "trace": trace})
            raise RuntimeError("非有限损失")
        loss.backward()
        gradient = model.sampler.density.weight.grad
        gradient_norm = 0. if gradient is None else gradient.norm().item()
        if not math.isfinite(gradient_norm):
            write_json(directory / "failure.json", {"step": step, "reason": "非有限梯度", "trace": trace})
            raise RuntimeError("非有限梯度")
        full_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 5.).item()
        optimizer.step()
        trace.append({"step": step, "loss": loss.item(), "sigma": sigma,
                      "density_gradient": gradient_norm, "full_gradient": full_norm})
        if step == 1 or step % args.log_every == 0 or step == args.steps:
            print(json.dumps({"run": directory.name, **trace[-1], "seconds": round(time.monotonic() - start_time, 1)}), flush=True)
    write_json(directory / "trace.json", trace)
    metrics, snapshots, records = {}, {}, {}
    for level, name in enumerate(DIFFICULTIES):
        metrics[name], snapshots[name], records[name] = evaluate(model, args, level, snapshot=True)
    write_json(directory / "metrics.json", metrics)
    write_json(directory / "snapshots.json", snapshots)
    write_json(directory / "predictions.json", records)
    torch.save(model.state_dict(), directory / "model.pt")
    plot_outputs(directory, args, trace, snapshots)
    write_json(directory / "complete.json", {"seconds": time.monotonic() - start_time,
                                             "final_step": args.steps, "checkpoint_selection": "固定最后一步"})
    print(json.dumps({"completed": directory.name, "metrics": {name: {k: metrics[name][k] for k in ("accuracy", "target_hit", "query_selectivity", "zero_signal_accuracy")} for name in metrics}}), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--method", choices=METHODS, default="adaptive")
    p.add_argument("--tokens", type=int, default=64)
    p.add_argument("--coarse", type=int, default=256)
    p.add_argument("--width", type=int, default=48)
    p.add_argument("--length", type=int, default=100000)
    p.add_argument("--event-width", type=int, default=1024)
    p.add_argument("--noise", type=float, default=.06)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--steps", type=int, default=600)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--eval-sequences", type=int, default=128)
    p.add_argument("--eval-seed", type=int, default=424242)
    p.add_argument("--train-seed-offset", type=int, default=100000)
    p.add_argument("--sigma", type=float, default=32.)
    p.add_argument("--anneal-fraction", type=float, default=.6)
    p.add_argument("--lr", type=float, default=.001)
    p.add_argument("--log-every", type=int, default=200)
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    p.add_argument("--output", type=Path, default=Path("results/phase2/main"))
    args = p.parse_args()
    if min(args.steps, args.batch_size, args.eval_sequences, args.tokens, args.coarse) < 1 or args.batch_size % 2 or args.eval_sequences % 2:
        p.error("步数和预算须为正数，批次与评估序列数须为偶数")
    torch.set_num_threads(4)
    args.data = DataConfig(length=args.length, event_width=args.event_width, noise=args.noise)
    train_run(args)


if __name__ == "__main__":
    main()
