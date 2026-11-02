"""冻结并执行第二阶段完整矩阵；已有结果只能续跑，禁止覆盖。"""
import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
from types import SimpleNamespace
import time

import torch

from phase2_data import DataConfig
from phase2_experiment import source_metadata, train_run, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/phase2/main"))
    parser.add_argument("--resume", action="store_true")
    opts = parser.parse_args()
    torch.set_num_threads(4)
    common = dict(width=48, length=100000, event_width=1024, noise=.06, steps=600,
                  batch_size=8, eval_sequences=128, eval_seed=424242, train_seed_offset=100000,
                  sigma=32., anneal_fraction=.6, lr=.001, log_every=200,
                  device="cuda" if torch.cuda.is_available() else "cpu")
    methods = ("adaptive", "query_blind", "uniform", "uniform_blur", "saliency", "no_blur", "oracle")
    runs = [dict(method=method, tokens=tokens, coarse=256, seed=seed)
            for tokens in (512, 64, 32) for seed in (7, 11, 23) for method in methods]
    runs += [dict(method="signal_time", tokens=32, coarse=256, seed=seed) for seed in (7, 11, 23)]
    runs += [dict(method="adaptive", tokens=32, coarse=1024, seed=seed) for seed in (7, 11, 23)]
    manifest = {"common": common, "runs": runs, "source": source_metadata(),
                "development": {"seed": 101, "eval_seed": 900001,
                                "change": "开发集将事件宽度 384 调整到 1024；完整测试集未用于选配置",
                                "failures_retained": ["smoke-v1", "smoke-longer", "smoke-width1024"]},
                "selection": "所有配置固定最后一步；不根据完整测试结果调整数据或模型",
                "auxiliary_loss": False}
    opts.output.mkdir(parents=True, exist_ok=True)
    manifest_path = opts.output / "frozen_manifest.json"
    if manifest_path.exists():
        recorded = json.loads(manifest_path.read_text())
        if not opts.resume or recorded != manifest:
            raise RuntimeError("已有冻结矩阵不一致，或没有指定 --resume")
    else:
        write_json(manifest_path, manifest)
    completion_path = opts.output / "sweep_complete.json"
    if opts.resume and completion_path.exists():
        completed = json.loads(completion_path.read_text())
        all_complete = all((opts.output / f"{r['method']}-t{r['tokens']}-c{r['coarse']}-s{r['seed']}" / "complete.json").exists() for r in runs)
        if not completed["failures"] and all_complete:
            print("冻结矩阵已全部完成，保留原始完成记录和耗时。", flush=True)
            return
    start = time.monotonic()
    failures = []
    for index, run in enumerate(runs):
        directory = opts.output / f"{run['method']}-t{run['tokens']}-c{run['coarse']}-s{run['seed']}"
        if opts.resume and (directory / "complete.json").exists():
            continue
        print(json.dumps({"index": index + 1, "total": len(runs), "start": directory.name}), flush=True)
        args = SimpleNamespace(**common, **run, output=opts.output,
                               data=DataConfig(length=common["length"], event_width=common["event_width"], noise=common["noise"]))
        try:
            # 每项实验完整控制台记录独立保存；主控制台只汇报进度。
            log_path = opts.output / f"{directory.name}.log"
            with log_path.open("x") as log, redirect_stdout(log):
                train_run(args)
            metrics = json.loads((directory / "metrics.json").read_text())
            print(json.dumps({"completed": directory.name,
                              "accuracy": {level: round(row["accuracy"], 4) for level, row in metrics.items()},
                              "strong_selectivity": round(metrics["strong"]["query_selectivity"], 6),
                              "elapsed_seconds": round(time.monotonic() - start, 1)}), flush=True)
        except Exception as exc:
            failures.append({"run": run, "error": repr(exc)})
            print(json.dumps({"failed": directory.name, "error": repr(exc)}), flush=True)
    write_json(opts.output / "sweep_complete.json", {"requested": len(runs), "failures": failures,
                                                    "seconds": time.monotonic() - start})
    if failures:
        raise RuntimeError(f"有 {len(failures)} 项失败，已保存记录")


if __name__ == "__main__":
    main()
