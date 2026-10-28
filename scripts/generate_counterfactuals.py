#!/usr/bin/env python3
"""生成答案保持不变、答案发生改变两类 TSRBench 反事实题。"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cf_ts.core import CounterfactualError, generate_variant  # noqa: E402

DEFAULT_SEED = ROOT / "data" / "source" / "seed100.jsonl"
DEFAULT_OUTPUT = ROOT / "data" / "generated" / "counterfactuals.jsonl"
DEFAULT_REPORT = ROOT / "reports" / "generation-summary.json"


def read_jsonl(path: Path):
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number} of {path}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--limit", type=int, default=None, help="Use only the first N seed rows for a development pilot")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if not args.seed.is_file():
        raise FileNotFoundError(args.seed)
    if args.output.exists() and not args.overwrite:
        raise FileExistsError(f"Refusing to overwrite {args.output}; pass --overwrite explicitly")

    seed_rows = list(read_jsonl(args.seed))
    if args.limit is not None:
        if args.limit <= 0:
            raise ValueError("--limit must be positive")
        seed_rows = seed_rows[:args.limit]

    variants = []
    skipped: list[dict[str, str]] = []
    for parent in seed_rows:
        for kind in ("answer_preserving", "answer_changing"):
            try:
                variants.append(generate_variant(parent, kind))
            except CounterfactualError as exc:
                # 有风险的题目应当跳过。报告会记录原因，不能为了凑数量硬生成
                # 一个不可信的反事实样本。
                skipped.append({"parent_id": str(parent.get("id")), "kind": kind, "reason": str(exc)})

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in variants:
            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")

    kind_counts = Counter(row["counterfactual"]["kind"] for row in variants)
    report = {
        "seed": str(args.seed),
        "output": str(args.output),
        "seed_rows": len(seed_rows),
        "generated_rows": len(variants),
        "generated_by_kind": dict(kind_counts),
        "skipped": skipped,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
