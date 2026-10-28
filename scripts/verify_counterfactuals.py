#!/usr/bin/env python3
"""独立重算并核验全部生成的反事实样本。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cf_ts.core import verify_variant  # noqa: E402

DEFAULT_SEED = ROOT / "data" / "source" / "seed100.jsonl"
DEFAULT_VARIANTS = ROOT / "data" / "generated" / "counterfactuals.jsonl"


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
    parser.add_argument("--variants", type=Path, default=DEFAULT_VARIANTS)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()
    if not args.seed.is_file() or not args.variants.is_file():
        raise FileNotFoundError("Both --seed and --variants must exist")

    parents = {row["id"]: row for row in read_jsonl(args.seed)}
    errors = []
    count = 0
    for variant in read_jsonl(args.variants):
        count += 1
        parent = parents.get(variant.get("parent_id"))
        if parent is None:
            errors.append({"id": variant.get("id"), "errors": ["unknown parent_id"]})
            continue
        row_errors = verify_variant(parent, variant)
        if row_errors:
            errors.append({"id": variant.get("id"), "errors": row_errors})
    report = {"seed_rows": len(parents), "variant_rows": count, "valid": not errors, "errors": errors}
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
