#!/usr/bin/env python3
"""不改动源数据，筛选两类干净的 TSRBench 公式题。"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cf_ts.core import (  # noqa: E402
    CounterfactualError,
    TRAFFIC_FAMILY,
    WIND_FAMILY,
    canonical_sha256,
    evaluate,
)

DEFAULT_SOURCE = ROOT.parent / "realtime-tslm" / "data" / "prepared" / "tsrbench-selected.jsonl"
DEFAULT_OUTPUT = ROOT / "data" / "source" / "seed100.jsonl"
DEFAULT_REPORT = ROOT / "reports" / "seed-selection.json"


def read_jsonl(path: Path):
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number} of {path}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if not args.source.is_file():
        raise FileNotFoundError(args.source)
    if args.output.exists() and not args.overwrite:
        raise FileExistsError(f"Refusing to overwrite {args.output}; pass --overwrite explicitly")

    selected = []
    skipped = 0
    for row in read_jsonl(args.source):
        if row.get("task") != "numerical_reasoning":
            continue
        try:
            result = evaluate(row)
        except CounterfactualError:
            skipped += 1
            continue
        if result.family not in {TRAFFIC_FAMILY, WIND_FAMILY}:
            continue
        # 保留原基准标签供溯源，但之后所有模型回答均按独立重算的选项下标评分。
        seed = dict(row)
        seed["dataset_answer_index"] = row.get("answer_index")
        seed["answer_index"] = result.choice_index
        seed["counterfactual_seed"] = {
            "family": result.family,
            "computed_target": result.target,
            "computed_choice_index": result.choice_index,
            "source_series_sha256": canonical_sha256(row["series"]),
        }
        selected.append(seed)

    counts = {family: sum(item["counterfactual_seed"]["family"] == family for item in selected)
              for family in (TRAFFIC_FAMILY, WIND_FAMILY)}
    if counts != {TRAFFIC_FAMILY: 50, WIND_FAMILY: 50}:
        raise RuntimeError(f"Expected exactly 50 clean rows per family, got {counts}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in selected:
            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    report = {
        "source": str(args.source),
        "output": str(args.output),
        "rows": len(selected),
        "family_counts": counts,
        # 这里是源文件字节级哈希，不是重新编码 JSON 后的哈希；可直接与旧项目
        # 的溯源记录进行对照。
        "source_sha256": hashlib.sha256(args.source.read_bytes()).hexdigest(),
        "output_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "non_supported_numeric_rows_skipped": skipped,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
