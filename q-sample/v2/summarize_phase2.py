"""汇总冻结的全部第二阶段结果，核验公平性并生成图表与失败案例。"""
import argparse
import csv
import json
from pathlib import Path
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).parent / "results"
MAIN = ROOT / "main"
OUT = ROOT / "analysis"


def load(path):
    return json.loads(path.read_text())


def main():
    global ROOT, MAIN, OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    ROOT, MAIN, OUT = args.root, args.root / "main", args.root / "analysis"
    manifest = load(MAIN / "frozen_manifest.json")
    completion = load(MAIN / "sweep_complete.json")
    if completion["failures"]:
        raise RuntimeError("矩阵存在失败运行，必须先明确处理并披露")
    rows, grouped = [], {}
    fingerprints = {}
    for run in manifest["runs"]:
        name = f"{run['method']}-t{run['tokens']}-c{run['coarse']}-s{run['seed']}"
        directory = MAIN / name
        config = load(directory / "config.json")
        assert config["source"] == manifest["source"], f"运行源码版本不一致：{name}"
        assert load(directory / "complete.json")["final_step"] == manifest["common"]["steps"]
        trace = load(directory / "trace.json")
        stability = {"max_density_gradient": max(t["density_gradient"] for t in trace),
                     "clipped_step_fraction": sum(t["full_gradient"] > 5 for t in trace) / len(trace),
                     "early_loss": statistics.mean(t["loss"] for t in trace[:50]),
                     "late_loss": statistics.mean(t["loss"] for t in trace[-50:])}
        for level, metrics in load(directory / "metrics.json").items():
            fingerprints.setdefault(level, set()).add(metrics["evaluation_sha256"])
            assert metrics["class_label_counts"] == [[64, 64]] * 4
            row = {**run, "difficulty": level, **metrics, **stability, "source": str(directory.relative_to(ROOT))}
            rows.append(row)
            key = (run["method"], run["tokens"], run["coarse"], level)
            grouped.setdefault(key, []).append(row)
    assert all(len(items) == 1 for items in fingerprints.values()), "方法或预算使用了不同评估信号"
    assert len(rows) == len(manifest["runs"]) * 3
    aggregates = []
    for (method, tokens, coarse, difficulty), group in grouped.items():
        assert sorted(g["seed"] for g in group) == [7, 11, 23]
        item = dict(method=method, tokens=tokens, coarse=coarse, difficulty=difficulty)
        for name, value in group[0].items():
            if isinstance(value, (float, int)) and name not in ("tokens", "coarse", "seed"):
                values = [g[name] for g in group]
                item[name] = {"mean": statistics.mean(values), "std": statistics.stdev(values), "values": values}
        aggregates.append(item)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "aggregate.json").write_text(json.dumps(aggregates, ensure_ascii=False, indent=2) + "\n")
    (OUT / "validation.json").write_text(json.dumps({"runs": len(manifest["runs"]), "metric_rows": len(rows),
                                                     "evaluation_fingerprints": {k: list(v)[0] for k, v in fingerprints.items()},
                                                     "balanced_each_query": True, "source_hashes_match": True}, indent=2) + "\n")
    with (OUT / "all_runs.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    def get(method, tokens, difficulty, coarse=256):
        return next(row for row in aggregates if (row["method"], row["tokens"], row["coarse"], row["difficulty"]) == (method, tokens, coarse, difficulty))

    methods = ("adaptive", "query_blind", "uniform", "uniform_blur", "saliency", "no_blur", "oracle")
    lines = ["| Tokens | 方法 | 无额外干扰 Acc | 少量干扰 Acc | 强干扰 Acc |", "|---:|---|---:|---:|---:|"]
    strong_lines = ["| Tokens | 方法 | Hit | ≥4 点覆盖 | Target Occ | Distractor Occ | Selectivity |", "|---:|---|---:|---:|---:|---:|---:|"]
    for tokens in (512, 64, 32):
        for method in methods:
            cells = []
            for difficulty in ("none", "few", "strong"):
                row = get(method, tokens, difficulty)
                cells.append(f"{100*row['accuracy']['mean']:.2f} ± {100*row['accuracy']['std']:.2f}")
            lines.append(f"| {tokens} | {method} | " + " | ".join(cells) + " |")
            row = get(method, tokens, "strong")
            values = [100 * row[key]["mean"] for key in ("target_hit", "target_four_points", "target_occupancy", "distractor_occupancy", "query_selectivity")]
            strong_lines.append(f"| {tokens} | {method} | " + " | ".join(f"{v:.3f}" for v in values) + " |")
    (OUT / "accuracy_table.md").write_text("\n".join(lines) + "\n")
    (OUT / "strong_evidence_table.md").write_text("\n".join(strong_lines) + "\n")
    differences = []
    for tokens in (512, 64, 32):
        for difficulty in ("none", "few", "strong"):
            for baseline in ("query_blind", "uniform_blur", "saliency"):
                a = get("adaptive", tokens, difficulty)
                b = get(baseline, tokens, difficulty)
                differences.append({"tokens": tokens, "difficulty": difficulty, "baseline": baseline,
                                    "accuracy_difference": [x-y for x, y in zip(a["accuracy"]["values"], b["accuracy"]["values"])],
                                    "selectivity_difference": [x-y for x, y in zip(a["query_selectivity"]["values"], b["query_selectivity"]["values"])]})
    (OUT / "paired_seed_differences.json").write_text(json.dumps(differences, indent=2) + "\n")

    fig, axes = plt.subplots(1, 3, figsize=(15, 4), constrained_layout=True)
    for ax, difficulty in zip(axes, ("none", "few", "strong")):
        for method in methods:
            mean = [100 * get(method, n, difficulty)["accuracy"]["mean"] for n in (32, 64, 512)]
            std = [100 * get(method, n, difficulty)["accuracy"]["std"] for n in (32, 64, 512)]
            ax.errorbar([32, 64, 512], mean, yerr=std, marker="o", label=method, capsize=2)
        ax.set(xscale="log", xticks=[32, 64, 512], xticklabels=[32, 64, 512], ylim=(40, 103), title=difficulty, xlabel="Tokens", ylabel="Accuracy (%)")
        ax.axhline(50, color="gray", ls="--", lw=.7)
    axes[-1].legend(fontsize=7, loc="upper left")
    fig.savefig(OUT / "accuracy.png", dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4), constrained_layout=True)
    for method_index, method in enumerate(methods):
        for tokens in (32, 64, 512):
            row = get(method, tokens, "strong")
            axes[0].scatter(row["target_hit"]["mean"] * 100, row["accuracy"]["mean"] * 100,
                            s=tokens / 3 + 18, color=f"C{method_index}", label=method if tokens == 32 else None)
    axes[0].set(xlabel="Target hit (%)", ylabel="Accuracy (%)", title="Strong distractors; size = token budget")
    axes[0].legend(fontsize=7)
    for method in ("adaptive", "query_blind", "saliency"):
        axes[1].errorbar([32, 64, 512], [100*get(method, n, "strong")["query_selectivity"]["mean"] for n in (32, 64, 512)],
                         yerr=[100*get(method, n, "strong")["query_selectivity"]["std"] for n in (32, 64, 512)], marker="o", label=method)
    axes[1].set(xscale="log", xticks=[32, 64, 512], xticklabels=[32, 64, 512], xlabel="Tokens", ylabel="Query selectivity (pp)")
    axes[1].axhline(0, color="gray", ls="--", lw=.7)
    axes[1].legend()
    fig.savefig(OUT / "evidence-and-selectivity.png", dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(1, 4, figsize=(15, 4), constrained_layout=True)
    for ax, method in zip(axes, ("adaptive", "query_blind", "saliency", "oracle")):
        snapshot = load(MAIN / f"{method}-t32-c256-s7" / "snapshots.json")["strong"]
        matrix = np.array(snapshot["occupancy_matrix"]) * 100
        ax.imshow(matrix, vmin=0, vmax=100, cmap="Blues")
        for i in range(4):
            for j in range(4):
                ax.text(j, i, f"{matrix[i,j]:.1f}", ha="center", va="center", fontsize=8,
                        color="white" if matrix[i,j] > 50 else "black")
        ax.set(title=method, xlabel=f"Candidate class; y={snapshot['labels']}", ylabel="Query class", xticks=range(4), yticks=range(4))
    fig.savefig(OUT / "paired-query-occupancy.png", dpi=160)
    plt.close(fig)

    failures = []
    for tokens in (32, 512):
        records = load(MAIN / f"adaptive-t{tokens}-c256-s7" / "predictions.json")["strong"]
        for record in records:
            for q, (label, probability) in enumerate(zip(record["labels"], record["probabilities"])):
                if int(probability >= .5) != label:
                    failures.append({"tokens": tokens, "query": q, "class": q, "sequence": record["sequence"],
                                     "label": label, "probability": probability,
                                     "target_samples": record["target_counts"][q],
                                     "source": f"main/adaptive-t{tokens}-c256-s7/predictions.json"})
            if len([x for x in failures if x["tokens"] == tokens]) >= 8:
                break
    (OUT / "failure_cases.json").write_text(json.dumps(failures, indent=2) + "\n")
    probe_rows = []
    probe_lines = ["| 粗分辨率 | 无额外干扰 Acc | 少量干扰 Acc | 强干扰 Acc | 强干扰双脉冲 Acc |", "|---:|---:|---:|---:|---:|"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    for index, coarse in enumerate((256, 1024)):
        records = [load(ROOT / "probes" / f"encoder-probe-c{coarse}-s{seed}" / "metrics.json") for seed in (7, 11, 23)]
        cells = []
        for difficulty in ("none", "few", "strong"):
            values = [r[difficulty]["accuracy"] for r in records]
            per_class = [statistics.mean(r[difficulty]["per_class_accuracy"][c] for r in records) for c in range(4)]
            probe_rows.append(dict(coarse=coarse, difficulty=difficulty, mean=statistics.mean(values),
                                   std=statistics.stdev(values), values=values, per_class_mean=per_class))
            cells.append(f"{100*statistics.mean(values):.2f} ± {100*statistics.stdev(values):.2f}")
        cells.append(f"{100*probe_rows[-1]['per_class_mean'][3]:.2f}")
        probe_lines.append(f"| {coarse} | " + " | ".join(cells) + " |")
        for seed in (7, 11, 23):
            trace = load(ROOT / "probes" / f"encoder-probe-c{coarse}-s{seed}" / "trace.json")
            axes[index].plot([r["step"] for r in trace], [r["loss"] for r in trace], lw=.6, label=f"seed {seed}")
        axes[index].set(title=f"Encoder probe, coarse={coarse}", xlabel="Update", ylabel="QA BCE")
        axes[index].legend(fontsize=8)
    fig.savefig(OUT / "encoder-probes.png", dpi=150)
    plt.close(fig)
    (OUT / "probes_aggregate.json").write_text(json.dumps(probe_rows, indent=2) + "\n")
    (OUT / "probe_table.md").write_text("\n".join(probe_lines) + "\n")
    budget_rows = []
    budget_lines = ["| Tokens | 查询盲窗口 Oracle：无额外干扰 | 少量干扰 | 强干扰 | 查询感知窗口 Oracle：强干扰 |", "|---:|---:|---:|---:|---:|"]
    for tokens in (32, 64, 512):
        records = [load(ROOT / "budget-probes" / f"blind-oracle-t{tokens}-s{seed}" / "metrics.json") for seed in (7, 11, 23)]
        cells = []
        for difficulty in ("none", "few", "strong"):
            assert all(r[difficulty]["evaluation_sha256"] in fingerprints[difficulty] for r in records)
            values = [r[difficulty]["accuracy"] for r in records]
            budget_rows.append(dict(tokens=tokens, difficulty=difficulty, mean=statistics.mean(values),
                                    std=statistics.stdev(values), values=values))
            cells.append(f"{100*statistics.mean(values):.2f} ± {100*statistics.stdev(values):.2f}")
        oracle = get("oracle", tokens, "strong")["accuracy"]
        cells.append(f"{100*oracle['mean']:.2f} ± {100*oracle['std']:.2f}")
        budget_lines.append(f"| {tokens} | " + " | ".join(cells) + " |")
    (OUT / "budget_probe_table.md").write_text("\n".join(budget_lines) + "\n")
    (OUT / "budget_probes_aggregate.json").write_text(json.dumps(budget_rows, indent=2) + "\n")
    fig, axes = plt.subplots(4, 1, figsize=(11, 6), constrained_layout=True)
    snapshot = load(ROOT / "budget-probes/blind-oracle-t32-s7/snapshots.json")["strong"]
    for q, ax in enumerate(axes):
        ax.vlines(snapshot["grid"][q], 0, 1, lw=.8)
        for start in snapshot["starts"]:
            ax.axvspan(start / 100000, (start + 1024) / 100000, color="gray", alpha=.2)
        ax.set(xlim=(0, 1), yticks=[], ylabel=f"Q{q}")
    axes[0].set_title("Query-blind window oracle: identical 32-token grids for all queries")
    axes[-1].set_xlabel("Normalized original time")
    fig.savefig(OUT / "blind-oracle-grids.png", dpi=150)
    plt.close(fig)
    print("\n".join(lines))
    print("Validation:", len(rows), "metric rows; identical evaluation signals; balanced labels; unchanged source")


if __name__ == "__main__":
    main()
