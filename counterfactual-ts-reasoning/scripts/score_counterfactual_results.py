#!/usr/bin/env python3
"""计算模型在原题和反事实题上的选项表现。

预测文件采用与模型无关的 JSONL 格式，每行包含 ``id`` 和
``predicted_choice_index`` 或 ``choice_index``。之后接入 ChatTS 时，只需
增加读取其输出的适配步骤，无须修改这里的评测定义。
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED = ROOT / "data" / "source" / "seed100.jsonl"
DEFAULT_VARIANTS = ROOT / "data" / "generated" / "counterfactuals.jsonl"


def read_jsonl(path: Path):
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number} of {path}") from exc


def accuracy(rows: list[dict], predictions: dict[str, int]) -> dict[str, int | float]:
    available = [row for row in rows if row["id"] in predictions]
    correct = sum(predictions[row["id"]] == row["answer_index"] for row in available)
    return {"scored": len(available), "correct": correct,
            "accuracy": correct / len(available) if available else None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--variants", type=Path, default=DEFAULT_VARIANTS)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()

    seed_rows = list(read_jsonl(args.seed))
    variant_rows = list(read_jsonl(args.variants))
    predictions: dict[str, int] = {}
    unparsed_predictions: list[str] = []
    for row in read_jsonl(args.predictions):
        prediction = row.get("predicted_choice_index", row.get("choice_index"))
        if prediction is None:
            unparsed_predictions.append(str(row.get("id")))
            continue
        if not isinstance(prediction, int):
            raise ValueError(f"Prediction {row.get('id')!r} lacks an integer choice index")
        if row.get("id") in predictions:
            raise ValueError(f"Duplicate prediction for {row.get('id')}")
        predictions[row["id"]] = prediction

    parents = {row["id"]: row for row in seed_rows}
    by_kind: dict[str, list[dict]] = defaultdict(list)
    for row in variant_rows:
        by_kind[row["counterfactual"]["kind"]].append(row)

    transition = {}
    for kind, rows in by_kind.items():
        conditioned = []
        successful = 0
        for row in rows:
            parent = parents.get(row["parent_id"])
            if parent is None or parent["id"] not in predictions or row["id"] not in predictions:
                continue
            # 只在原题答对时统计迁移关系，才能把证据敏感性与普通答错区分开。
            if predictions[parent["id"]] != parent["answer_index"]:
                continue
            conditioned.append(row)
            if kind == "answer_preserving":
                successful += predictions[row["id"]] == predictions[parent["id"]]
            else:
                successful += predictions[row["id"]] == row["answer_index"]
        transition[kind] = {
            "conditioned_on_correct_parent": len(conditioned),
            "successful": successful,
            "rate": successful / len(conditioned) if conditioned else None,
        }

    report = {
        "source_accuracy": accuracy(seed_rows, predictions),
        "counterfactual_accuracy": {kind: accuracy(rows, predictions) for kind, rows in by_kind.items()},
        "transition_metrics": transition,
        "prediction_rows": len(predictions),
        "unparsed_prediction_ids": unparsed_predictions,
        "unparsed_prediction_count": len(unparsed_predictions),
    }
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
