#!/usr/bin/env python3
"""构造覆盖交通、风电及两类反事实关系的小型冒烟测试集。"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED = ROOT / "data" / "source" / "seed100.jsonl"
DEFAULT_VARIANTS = ROOT / "data" / "generated" / "counterfactuals.jsonl"
DEFAULT_OUTPUT = ROOT / "data" / "generated" / "smoke_input.jsonl"


def read_jsonl(path: Path):
    """读取 JSONL 文件，并在异常时指出具体位置。"""

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path} 的第 {line_number} 行不是有效 JSON") from exc


def stable_key(identifier: str, seed: str) -> str:
    """返回可复现的抽样排序键，避免每次冒烟集都不同。"""

    return hashlib.sha256(f"{seed}:{identifier}".encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--variants", type=Path, default=DEFAULT_VARIANTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--parents-per-family", type=int, default=4)
    parser.add_argument("--selection-seed", default="chatts-smoke-v1")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.parents_per_family <= 0:
        raise ValueError("--parents-per-family 必须为正数")
    if args.output.exists() and not args.overwrite:
        raise FileExistsError(f"拒绝覆盖 {args.output}；如确认需要，请显式加入 --overwrite")

    parents = list(read_jsonl(args.seed))
    variants_by_parent: dict[str, list[dict]] = defaultdict(list)
    for variant in read_jsonl(args.variants):
        variants_by_parent[variant["parent_id"]].append(variant)

    by_family: dict[str, list[dict]] = defaultdict(list)
    for parent in parents:
        family = parent["counterfactual_seed"]["family"]
        # 只使用同时具备两种变体的父题，保证冒烟集的关系完整。
        kinds = {item["counterfactual"]["kind"] for item in variants_by_parent[parent["id"]]}
        if {"answer_preserving", "answer_changing"} <= kinds:
            by_family[family].append(parent)

    chosen = []
    for family, rows in sorted(by_family.items()):
        selected = sorted(rows, key=lambda row: stable_key(row["id"], args.selection_seed))[:args.parents_per_family]
        if len(selected) != args.parents_per_family:
            raise RuntimeError(f"{family} 中没有足够的完整父题")
        chosen.extend(selected)

    output_rows = []
    for parent in chosen:
        output_rows.append(parent)
        # 固定排序方便人读日志，也保证每个父题都紧跟着两条变体。
        output_rows.extend(sorted(variants_by_parent[parent["id"]], key=lambda row: row["counterfactual"]["kind"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in output_rows:
            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    print(json.dumps({
        "output": str(args.output),
        "parents": len(chosen),
        "rows": len(output_rows),
        "families": sorted(by_family),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
