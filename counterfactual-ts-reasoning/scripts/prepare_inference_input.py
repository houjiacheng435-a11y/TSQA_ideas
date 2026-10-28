#!/usr/bin/env python3
"""将原题和反事实题合并为一个推理用 JSONL 输入。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED = ROOT / "data" / "source" / "seed100.jsonl"
DEFAULT_VARIANTS = ROOT / "data" / "generated" / "counterfactuals.jsonl"
DEFAULT_OUTPUT = ROOT / "data" / "generated" / "inference_input.jsonl"


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
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and not args.overwrite:
        raise FileExistsError(f"Refusing to overwrite {args.output}; pass --overwrite explicitly")

    rows = [*read_jsonl(args.seed), *read_jsonl(args.variants)]
    ids = [row.get("id") for row in rows]
    if len(ids) != len(set(ids)) or any(not item for item in ids):
        raise ValueError("Every inference row needs one unique non-empty id")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    print(json.dumps({"output": str(args.output), "rows": len(rows)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
