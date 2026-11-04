"""只读核验官方元数据、CSV 指纹、标签粒度与可观察的内容重叠。"""
import argparse
import hashlib
import importlib.util
import itertools
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
CANDIDATES = ("Shape Identification", "Temporal Localization", "Interval Discovery")


def load(name):
    return json.loads((HERE / "sources" / name).read_text())


def stats(values):
    return dict(zip(("min", "median", "max"), map(float, np.quantile(values, [0, .5, 1])))) if values else None


def query_window(task):
    # 优先读取题目明确写出的时间，不读取答案推导搜索范围。
    question = task["question"].split("(Output format")[0]
    times = re.findall(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", question)
    if len(times) >= 2:
        return pd.Timestamp(times[0]), pd.Timestamp(times[1]), "second"
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", question)
    if len(dates) >= 2:
        return pd.Timestamp(dates[0]), pd.Timestamp(dates[1]) + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1), "date_ambiguous"
    months = re.findall(r"\d{4}-\d{2}", question)
    if months:
        start = pd.Timestamp(months[0] + "-01")
        return start, start + pd.offsets.MonthBegin(1) - pd.Timedelta(nanoseconds=1), "month"
    years = re.findall(r"\b20\d{2}\b", question)
    if years:
        return pd.Timestamp(years[0] + "-01-01"), pd.Timestamp(str(int(years[0]) + 1) + "-01-01") - pd.Timedelta(nanoseconds=1), "year"
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=HERE.parents[2])
    parser.add_argument("--vendor", type=Path, default=HERE.parents[2] / "vendor/Sonar-TS-v016-direct")
    args = parser.parse_args()
    datasets = {"test": load("NLQTSBench-tasks.json"), "train": load("NLQTSBench-train-tasks.json"),
                "train_v2_general": load("train-v2-general-tasks.json"), "train_v2_composite": load("train-v2-composite_trend-tasks.json")}
    datasets["train_v2"] = datasets["train_v2_general"] + datasets["train_v2_composite"]
    result = {"datasets": {}, "overlap": {}, "csv": [], "source_overlap": [], "limitations": ["未下载全部 CSV，未验证全库逐行近重复", "同通道不自动证明同源，同文件不同也不能排除共享背景", "题目仅给日期时搜索端点存在精度歧义"]}
    spec = importlib.util.spec_from_file_location("official_evaluator", args.vendor / "sonar_ts/evaluator.py")
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    for name, tasks in datasets.items():
        info = {"n": len(tasks), "subtasks": dict(Counter(t["subtask"] for t in tasks)),
                "metrics": dict(Counter(t["eval_metric"] for t in tasks)),
                "meta_count": sum("meta" in t for t in tasks), "candidate_tasks": {}}
        for subtask in CANDIDATES:
            subset = [t for t in tasks if t["subtask"] == subtask]
            spans = [(t, evaluator.parse_interval(t["ground_truth"])) for t in subset if t["eval_metric"] == "iou"]
            info["candidate_tasks"][subtask] = {"n": len(subset), "ground_truth_types": dict(Counter(type(t["ground_truth"]).__name__ for t in subset)),
                "valid_intervals": sum(s is not None for t, s in spans), "degenerate_ids": [t["id"] for t, s in spans if s and s[0] == s[1]],
                "duration_seconds": stats([(s[1]-s[0]).total_seconds() for t, s in spans if s]),
                "question_window_precision": dict(Counter(query_window(t)[2] if query_window(t) else "unknown" for t in subset))}
        info["official_answer_self_scores"] = dict(Counter(round(evaluator.score_one(t["eval_metric"], t["answer"], t["ground_truth"])[0], 10) for t in tasks))
        result["datasets"][name] = info
    for name in ("general", "composite_trend"):
        split = load(f"train-v2-{name}-splits.json")
        tasks = {t["id"]: t for t in datasets["train_v2_" + ("general" if name == "general" else "composite") ]}
        result.setdefault("official_splits", {})[name] = {k: dict(n=len(ids), subtasks=dict(Counter(tasks[i]["subtask"] for i in ids)), ids=ids) for k, ids in split.items()}
    for a, b in itertools.combinations(("train", "train_v2", "test"), 2):
        left, right = datasets[a], datasets[b]
        pairs = [(x, y) for x in left for y in right if x["question"] == y["question"]]
        result["overlap"][a + "__" + b] = {"id_count": len({t["id"] for t in left} & {t["id"] for t in right}),
            "exact_question_pairs": [dict(left=x["id"], right=y["id"], same_gt=x["ground_truth"] == y["ground_truth"]) for x, y in pairs],
            "shared_channel_names": sorted({str(t["channel"]) for t in left} & {str(t["channel"]) for t in right})}
    trees = {name: load(repo + "-tree.json") for name, repo in (("test", "NLQTSBench"), ("train", "NLQTSBench-train"), ("train_v2", "NLQTSBench-train-v2"))}
    remote = {}
    for name, tree in trees.items():
        files = [x for x in tree if x["path"].endswith(".csv")]
        result["datasets"][name]["remote_csv_count"] = len(files)
        result["datasets"][name]["remote_csv_bytes"] = sum(x["size"] for x in files)
        assert len(files) == len(datasets[name]), (name, len(files))
        remote[name] = {Path(x["path"]).stem: x for x in files}
    for a, b in itertools.combinations(("train", "train_v2", "test"), 2):
        inverse = defaultdict(list)
        for tid, record in remote[b].items():
            inverse[record["oid"]].append(tid)
        pairs = [(tid, other) for tid, record in remote[a].items() for other in inverse[record["oid"]]]
        result["overlap"]["__".join(sorted((a, b), key=("train", "train_v2", "test").index))]["exact_csv_blob_pairs"] = pairs
    # 额外给出受影响任务数；文件对数不能误当成独立样本数。
    for key, record in result["overlap"].items():
        pairs = record["exact_csv_blob_pairs"]
        record["exact_csv_left_tasks"] = len({a for a,b in pairs})
        record["exact_csv_right_tasks"] = len({b for a,b in pairs})
    local = defaultdict(list)
    for path in args.workspace.rglob("*.csv"):
        if any(path.stem in records for records in remote.values()):
            local[path.stem].append(path)
    frames = {}
    for name, tasks in ((n, datasets[n]) for n in remote):
        available = []
        for task in tasks:
            candidates = local.get(task["id"], [])
            verified = []
            for path in candidates:
                data = path.read_bytes()
                oid = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
                if oid == remote[name][task["id"]]["oid"]:
                    verified.append(path)
            if not verified:
                continue
            available.append(task["id"])
            path = verified[0]
            frame = pd.read_csv(path)
            times = pd.to_datetime(frame.iloc[:, 0])
            values = frame.iloc[:, 1:].apply(pd.to_numeric, errors="coerce")
            frame.index = pd.DatetimeIndex(times)
            frames[name, task["id"]] = frame.iloc[:, 1:]
            delta = times.diff().dt.total_seconds().dropna()
            entry = dict(dataset=name, id=task["id"], subtask=task["subtask"], path=str(path), copies=len(verified),
                         rows=len(frame), channels=list(values.columns), channel_count=len(values.columns),
                         first=str(times.iloc[0]), last=str(times.iloc[-1]), dt_seconds=stats(delta.tolist()),
                         duplicate_timestamps=int(times.duplicated().sum()), nonfinite=int((~np.isfinite(values.to_numpy())).sum()),
                         sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            window = query_window(task)
            if window:
                start, end, precision = window
                entry["query_rows"] = int(((times >= start) & (times <= end)).sum())
                entry["query_precision"] = precision
            if task["subtask"] in CANDIDATES:
                gt = task["ground_truth"] if isinstance(task["ground_truth"], list) else [task["ground_truth"]]
                ends = pd.to_datetime(gt)
                entry["gt_endpoints_on_grid"] = [bool((times == t).any()) for t in ends]
                entry["target_rows"] = int(((times >= ends[0]) & (times <= ends[-1])).sum())
                entry["target_fraction_full"] = entry["target_rows"] / len(frame)
                entry["uniform_target_expected"] = {str(n): n * entry["target_fraction_full"] for n in (32,64,512)}
            result["csv"].append(entry)
        result["datasets"][name]["local_verified_ids"] = available
    # 对实际已有 CSV 做时间对齐数值比较；这比只比较任务 ID 更严格。
    for (name, tid), frame in frames.items():
        if name == "test":
            continue
        for (other_name, other_id), other in frames.items():
            if other_name != "test":
                continue
            for channel in frame.columns.intersection(other.columns):
                common = frame.index.intersection(other.index)
                if len(common) < 20:
                    continue
                equal = np.isclose(frame.loc[common, channel], other.loc[common, channel], rtol=0, atol=1e-12)
                result["source_overlap"].append(dict(dataset=name, id=tid, test_id=other_id, channel=channel,
                    shared_rows=len(common), equal_fraction=float(equal.mean()), equal_rows=int(equal.sum())))
    # 查找官方数据中可直接复用的同 CSV 多问题，不人为制造新问题。
    result["paired_exact_csv_groups"] = {}
    result["paired_candidate_diagnostics"] = {}
    for name in remote:
        groups = defaultdict(list)
        for tid, record in remote[name].items():
            groups[record["oid"]].append(tid)
        result["paired_exact_csv_groups"][name] = [v for v in groups.values() if len(v)>1]
        by_id = {t["id"]: t for t in datasets[name]}
        candidate_groups = [[by_id[i] for i in ids if by_id[i]["subtask"] in CANDIDATES] for ids in groups.values()]
        candidate_groups = [g for g in candidate_groups if len(g)>1]
        diagnostic = []
        for group in candidate_groups:
            endpoints = sorted({str(ts) for t in group for ts in (t["ground_truth"] if isinstance(t["ground_truth"],list) else [t["ground_truth"]])})
            diagnostic.append(dict(ids=[t["id"] for t in group], distinct_answers=len({json.dumps(t["ground_truth"]) for t in group}),
                                   endpoint_count=len(endpoints), endpoints=endpoints,
                                   blind_coordinate_oracle_fits={str(n):len(endpoints)<=n for n in (32,64,512)}))
        result["paired_candidate_diagnostics"][name] = diagnostic
    # 同指纹的其他题直接复用已测行数，不再次下载同一信号。
    known_shapes = {}
    for record in result["csv"]:
        known_shapes[remote[record["dataset"]][record["id"]]["oid"]] = {k:record[k] for k in ("rows", "channel_count", "first", "last")}
    result["lengths_by_verified_shared_blob"] = {name: {tid: known_shapes[rec["oid"]] for tid,rec in records.items() if rec["oid"] in known_shapes} for name,records in remote.items()}
    # 这是建议的内部源分组划分，不替代官方拆分、不改写官方题目。
    candidates = [t for t in datasets["train_v2"] if t["subtask"] in CANDIDATES]
    channels = sorted({str(t["channel"]) for t in candidates}, key=lambda c: hashlib.sha256(("20261104:"+c).encode()).hexdigest())
    n_train, n_valid = int(.7*len(channels)), max(1,int(.15*len(channels)))
    groups = {"train": channels[:n_train], "valid": channels[n_train:n_train+n_valid], "holdout":channels[n_train+n_valid:]}
    proposed = {name:[t["id"] for t in candidates if str(t["channel"]) in cs] for name,cs in groups.items()}
    result["proposed_channel_split"] = {name:dict(channels=cs, ids=proposed[name], n=len(proposed[name]), subtasks=dict(Counter(t["subtask"] for t in candidates if t["id"] in proposed[name]))) for name,cs in groups.items()}
    result["split_status"] = "仅建议：通道名隔离尚不是上游源文件隔离，完整近重复审计通过前不可开训"
    result["test_exposure"] = {"all_metadata_labels_inspected": True,
        "previous_existing_raw_csv_ids_conservatively_exposed": result["datasets"]["test"]["local_verified_ids"],
        "used_for_training": False,
        "note": "历史原始 CSV 全部保守记为已接触；并不声称每个文件都已用于模型实验，也不把其余测试题称为完全未见"}
    result["official_evaluator_sha256"] = hashlib.sha256((args.vendor / "sonar_ts/evaluator.py").read_bytes()).hexdigest()
    (HERE / "audit_results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({"counts": {k: v["n"] for k,v in result["datasets"].items()}, "local_verified": {k: len(v.get("local_verified_ids", [])) for k,v in result["datasets"].items()}, "csv_profiles": len(result["csv"]), "source_pairs": len(result["source_overlap"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
