"""汇总已记录的三个随机种子的预实验结果，不筛选模型检查点。"""
import json
from pathlib import Path
import statistics


def main():
    root = Path(__file__).parent
    result_root = root / "results"
    methods = ("adaptive", "uniform", "adaptive_no_blur", "adaptive_mean_only", "adaptive_query_blind")
    rows, sources = [], []
    for name in methods:
        results = []
        for seed in (7, 11, 23):
            directory = f"queryblind-seed{seed}" if seed == 7 and name == "adaptive_query_blind" else f"signal-seed{seed}"
            path = result_root / directory / f"{name}.json"
            data = json.loads(path.read_text())
            results.append(data["final"])
            sources.append(str(path.relative_to(root)))
        row = {"method": name, "seeds": [7, 11, 23]}
        for metric in ("accuracy", "target_hit", "target_occupancy", "target_mass", "value_zero_accuracy", "query_target_occupancy_change"):
            values = [item[metric] for item in results]
            row[metric] = {"mean": statistics.mean(values), "std": statistics.stdev(values), "values": values}
        rows.append(row)
    (result_root / "aggregate.json").write_text(json.dumps({"sources": sources, "rows": rows}, indent=2) + "\n")
    lines = ["| 方法 | QA 准确率（均值±种子间标准差） | 正例事件命中率 | 目标区采样占比 |", "|---|---:|---:|---:|"]
    for row in rows:
        acc = row["accuracy"]
        lines.append(f"| `{row['method']}` | {100*acc['mean']:.2f}% ± {100*acc['std']:.2f} | "
                     f"{100*row['target_hit']['mean']:.2f}% | {100*row['target_occupancy']['mean']:.4f}% |")
    table = "\n".join(lines)
    (result_root / "table.md").write_text(table + "\n")
    print(table)


if __name__ == "__main__":
    main()
