"""Controlled synthetic task; labels supervise only the binary answer head."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch
from torch.nn import functional as F

from model import SyntheticQA


def batch(args, generator, size=None):
    size = size or args.batch_size
    device = args.device
    x = torch.randn(size, args.length, 1, generator=generator, device=device) * args.noise
    query = (torch.randint(0, 2, (size, 1), generator=generator, device=device) * 2 - 1).float()
    labels = torch.randint(0, 2, (size,), generator=generator, device=device).float()
    # Two separated, random positions. Every sample has an opposite-sign distractor.
    low = torch.randint(args.event_width, args.length // 2 - args.event_width,
                        (size,), generator=generator, device=device)
    high = torch.randint(args.length // 2 + args.event_width,
                         args.length - 2 * args.event_width,
                         (size,), generator=generator, device=device)
    swap = torch.randint(0, 2, (size,), generator=generator, device=device).bool()
    target = torch.where(swap, high, low)
    distractor = torch.where(swap, low, high)
    offset = torch.arange(args.event_width, device=device)[None, :]
    rows = torch.arange(size, device=device)[:, None]
    x[rows, target[:, None] + offset, 0] += args.amplitude * query * labels[:, None]
    x[rows, distractor[:, None] + offset, 0] -= args.amplitude * query
    return x, query, labels, target, distractor


def region_metrics(result, start, args):
    positions = result["grid"] * (args.length - 1)
    inside = (positions >= start[:, None]) & (positions <= start[:, None] + args.event_width - 1)
    occupancy = inside.float().mean(-1)
    index = start[:, None] + torch.arange(args.event_width, device=args.device)[None]
    mass = result["mass"].gather(1, index).sum(-1)
    return occupancy, mass, inside.any(-1).float()


@torch.no_grad()
def evaluate(model, args, mode):
    model.eval()
    generator = torch.Generator(device=args.device).manual_seed(100000 + args.seed)
    sums = dict(loss=0., accuracy=0., target_occupancy=0., target_mass=0., target_hit=0.,
                distractor_occupancy=0., query_target_occupancy_change=0.,
                value_zero_accuracy=0., uniform_grid_accuracy=0.)
    total = positive = 0
    for _ in range(args.eval_batches):
        x, query, labels, target, distractor = batch(args, generator)
        result = model(x, query, mode=mode)  # Always evaluate the raw signal.
        zero = model(x, query, mode=mode, value_mode="zero")
        uniform = model(x, query, mode="uniform")
        opposite = model(x, -query, mode=mode)
        mask = labels.bool()
        occupancy, mass, hit = region_metrics(result, target, args)
        distractor_occupancy, _, _ = region_metrics(result, distractor, args)
        flipped_occupancy, _, _ = region_metrics(opposite, target, args)
        n = labels.numel()
        sums["loss"] += F.binary_cross_entropy_with_logits(result["logits"], labels, reduction="sum").item()
        for key, pred in (("accuracy", result), ("value_zero_accuracy", zero),
                          ("uniform_grid_accuracy", uniform)):
            sums[key] += ((pred["logits"] >= 0) == mask).sum().item()
        for key, values in (("target_occupancy", occupancy), ("target_mass", mass),
                            ("target_hit", hit), ("distractor_occupancy", distractor_occupancy),
                            ("query_target_occupancy_change", occupancy - flipped_occupancy)):
            sums[key] += values[mask].sum().item()
        total += n
        positive += mask.sum().item()
    for key in sums:
        sums[key] /= total if key in ("loss", "accuracy", "value_zero_accuracy", "uniform_grid_accuracy") else max(1, positive)
    sums.update(examples=total, positive_examples=positive)
    model.train()
    return sums


@torch.no_grad()
def snapshot(model, args, mode):
    generator = torch.Generator(device=args.device).manual_seed(100000 + args.seed)
    x, query, labels, target, distractor = batch(args, generator)
    index = int(labels.argmax().item())
    result = model(x, query, mode=mode)
    opposite = model(x, -query, mode=mode)
    return {
        "signal": x[index, ::max(1, args.length // 10000), 0].cpu().tolist(),
        "query": query[index].item(), "target": target[index].item(),
        "distractor": distractor[index].item(), "label": labels[index].item(),
        "coarse_mass": result["coarse_mass"][index].cpu().tolist(),
        "grid": result["grid"][index].cpu().tolist(),
        "opposite_coarse_mass": opposite["coarse_mass"][index].cpu().tolist(),
    }


def plot_run(args, name, trace, initial, final, output):
    fig, axes = plt.subplots(4, 1, figsize=(11, 11), constrained_layout=True)
    axes[0].plot([r["step"] for r in trace], [r["loss"] for r in trace])
    axes[0].set(ylabel="Training BCE", xlabel="Update")
    axes[1].plot(torch.linspace(0, 1, len(final["signal"])), final["signal"], lw=.5)
    axes[1].set(ylabel="Raw signal")
    axis = (torch.arange(len(final["coarse_mass"])) + .5) / len(final["coarse_mass"])
    axes[2].plot(axis, initial["coarse_mass"], label="Initial query density")
    axes[2].plot(axis, final["coarse_mass"], label="Trained query density")
    axes[2].plot(axis, final["opposite_coarse_mass"], label="Opposite query density", alpha=.7)
    axes[2].legend()
    axes[2].set(ylabel="Coarse probability mass")
    axes[3].eventplot([initial["grid"], final["grid"]], lineoffsets=[1, 0], linelengths=.6)
    axes[3].set(yticks=[0, 1], yticklabels=["Trained", "Initial"], xlabel="Normalized original time")
    for ax in axes[1:]:
        ax.axvspan(final["target"] / args.length,
                   (final["target"] + args.event_width) / args.length, color="green", alpha=.3)
        ax.axvspan(final["distractor"] / args.length,
                   (final["distractor"] + args.event_width) / args.length, color="red", alpha=.3)
        ax.set_xlim(0, 1)
    fig.suptitle(f"{name}: query sign {final['query']:+.0f}; green=target, red=distractor")
    fig.savefig(output / f"{name}.png", dpi=160)
    plt.close(fig)


def train(args, name, output):
    torch.manual_seed(args.seed)
    model = SyntheticQA(readout=args.readout, coarse=args.coarse, tokens=args.tokens, width=args.width,
                        epsilon=args.epsilon, statistics=name != "adaptive_mean_only").to(args.device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    generator = torch.Generator(device=args.device).manual_seed(200000 + args.seed)
    mode = name if name in ("uniform", "adaptive_query_blind") else "adaptive"
    initial_metrics = evaluate(model, args, mode)
    initial = snapshot(model, args, mode)
    trace = []
    start = time.monotonic()
    for step in range(1, args.steps + 1):
        sigma = args.sigma * max(0., 1 - (step - 1) / max(1, args.steps * args.anneal_fraction))
        if name in ("adaptive_no_blur", "uniform"):
            sigma = 0.
        x, query, labels, _, _ = batch(args, generator)
        optimizer.zero_grad(set_to_none=True)
        result = model(x, query, mode=mode, sigma=sigma)
        loss = F.binary_cross_entropy_with_logits(result["logits"], labels)
        if not torch.isfinite(loss):
            raise RuntimeError(f"Non-finite loss at {name} step {step}")
        loss.backward()
        grad = model.sampler.density.weight.grad
        grad_norm = 0. if grad is None else grad.norm().item()
        if not math.isfinite(grad_norm):
            raise RuntimeError(f"Non-finite density gradient at {name} step {step}")
        torch.nn.utils.clip_grad_norm_(model.parameters(), 5.)
        optimizer.step()
        row = {"step": step, "loss": loss.item(), "sigma": sigma, "density_grad_norm": grad_norm}
        trace.append(row)
        if step == 1 or step % args.log_every == 0 or step == args.steps:
            print(json.dumps({"run": name, **row, "seconds": round(time.monotonic() - start, 1)}), flush=True)
    final_metrics = evaluate(model, args, mode)
    final = snapshot(model, args, mode)
    result = {"name": name, "initial": initial_metrics, "final": final_metrics,
              "seconds": time.monotonic() - start,
              "initial_snapshot": initial, "final_snapshot": final, "trace": trace}
    (output / f"{name}.json").write_text(json.dumps(result, indent=2) + "\n")
    torch.save(model.state_dict(), output / f"{name}.pt")
    plot_run(args, name, trace, initial, final, output)
    print(json.dumps({"run": name, "final": final_metrics}), flush=True)
    return {key: result[key] for key in ("name", "initial", "final", "seconds")}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--length", type=int, default=100000)
    p.add_argument("--event-width", type=int, default=50)
    p.add_argument("--tokens", type=int, default=512)
    p.add_argument("--coarse", type=int, default=256)
    p.add_argument("--width", type=int, default=48)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--steps", type=int, default=300)
    p.add_argument("--eval-batches", type=int, default=16)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--noise", type=float, default=.1)
    p.add_argument("--amplitude", type=float, default=2.)
    p.add_argument("--epsilon", type=float, default=1e-4)
    p.add_argument("--sigma", type=float, default=128.)
    p.add_argument("--anneal-fraction", type=float, default=.6)
    p.add_argument("--lr", type=float, default=2e-3)
    p.add_argument("--log-every", type=int, default=50)
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    p.add_argument("--threads", type=int, default=4)
    p.add_argument("--readout", choices=["signal", "signal_time", "signal_time_detached"], default="signal")
    p.add_argument("--runs", nargs="+", choices=["adaptive", "uniform", "adaptive_no_blur", "adaptive_mean_only", "adaptive_query_blind"],
                   default=["adaptive", "uniform", "adaptive_no_blur"])
    p.add_argument("--output", type=Path, default=Path("results/pilot"))
    args = p.parse_args()
    if args.length <= 8 * args.event_width or min(args.steps, args.batch_size, args.eval_batches) < 1:
        p.error("Need length > 8 * event_width and positive steps/batch/eval counts")
    torch.set_num_threads(args.threads)
    args.output.mkdir(parents=True, exist_ok=True)
    config = {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}
    config.update(torch_version=torch.__version__, gpu=torch.cuda.get_device_name() if args.device.startswith("cuda") else None,
                  task=f"Query asks whether a positive/negative width-{args.event_width} square pulse exists; opposite-sign distractor always present",
                  training_supervision="Answer BCE only; event coordinates used solely for evaluation",
                  source_sha256={name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                 for name in ("model.py", "train_synthetic.py")})
    (args.output / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    runs = [train(args, name, args.output) for name in args.runs]
    (args.output / "summary.json").write_text(json.dumps(runs, indent=2) + "\n")


if __name__ == "__main__":
    main()
