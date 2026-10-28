#!/usr/bin/env python3
"""冻结本轮实验输入的哈希、题目ID和类别计数。"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED = ROOT / "data" / "source" / "seed100.jsonl"
DEFAULT_VARIANTS = ROOT / "data" / "generated" / "counterfactuals.jsonl"
DEFAULT_INPUT = ROOT / "data" / "generated" / "inference_input.jsonl"
DEFAULT_OUTPUT = ROOT / "reports" / "input-manifest-v1.json"


def sha256_file(path: Path) -> str:
    """计算文件的字节级 SHA-256。"""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    """读取 JSONL，并拒绝空ID或重复ID。"""

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    identifiers = [row.get("id") for row in rows]
    if any(not value for value in identifiers) or len(identifiers) != len(set(identifiers)):
        raise ValueError(f"{path} 含有空ID或重复ID")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--variants", type=Path, default=DEFAULT_VARIANTS)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"冻结清单已存在：{args.output}；不要直接覆盖它")
    for path in (args.seed, args.variants, args.input):
        if not path.is_file():
            raise FileNotFoundError(path)

    seed_rows, variant_rows, input_rows = (read_jsonl(path) for path in (args.seed, args.variants, args.input))
    expected_ids = [row["id"] for row in seed_rows] + [row["id"] for row in variant_rows]
    if [row["id"] for row in input_rows] != expected_ids:
        raise ValueError("完整推理输入的ID顺序或内容与原题、反事实题不一致")
    family_counts = Counter(row["counterfactual_seed"]["family"] for row in seed_rows)
    variant_counts = Counter(
        (row["counterfactual"]["family"], row["counterfactual"]["kind"])
        for row in variant_rows
    )
    manifest = {
        "kind": "counterfactual_ts_reasoning_input_manifest_v1",
        "seed": {"path": str(args.seed), "sha256": sha256_file(args.seed), "rows": len(seed_rows),
                 "family_counts": dict(sorted(family_counts.items()))},
        "variants": {"path": str(args.variants), "sha256": sha256_file(args.variants), "rows": len(variant_rows),
                     "family_kind_counts": {f"{family}/{kind}": count for (family, kind), count in sorted(variant_counts.items())}},
        "inference_input": {"path": str(args.input), "sha256": sha256_file(args.input), "rows": len(input_rows),
                            "first_id": input_rows[0]["id"], "last_id": input_rows[-1]["id"]},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
