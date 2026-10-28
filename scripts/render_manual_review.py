#!/usr/bin/env python3
"""把反事实样本渲染成适合人工抽查的 Markdown 报告。

原始 JSONL 中一条时序可能含数十个数值，不适合直接在编辑器里逐行查看。
本脚本只展示人工判断修改是否合理所需的信息：题目、选项、正确答案、修改
位置和序列统计量。它不参与标签生成，也不替代独立公式核验。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED = ROOT / "data" / "source" / "seed100.jsonl"
DEFAULT_VARIANTS = ROOT / "data" / "generated" / "counterfactuals.jsonl"
DEFAULT_OUTPUT = ROOT / "reports" / "manual-review-20.md"


def read_jsonl(path: Path):
    """逐行读取 JSONL，并在损坏文件时报告具体行号。"""

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path} 的第 {line_number} 行不是有效 JSON") from exc


def number(value: float) -> str:
    """以紧凑但不丢失主要信息的形式显示数值。"""

    return f"{float(value):.6g}"


def channel_statistics(values: list[float]) -> str:
    """返回长度、最小值、最大值和总和，避免完整展开长序列。"""

    numeric = [float(value) for value in values]
    return (
        f"长度={len(numeric)}，最小={number(min(numeric))}，"
        f"最大={number(max(numeric))}，总和={number(sum(numeric))}"
    )


def stable_order_key(row: dict, review_seed: str) -> str:
    """用稳定哈希抽取样本，保证每次生成的20题相同。"""

    text = f"{review_seed}:{row['id']}".encode("utf-8")
    return hashlib.sha256(text).hexdigest()


def option_label(index: int) -> str:
    """将0开始的选项下标转成 A、B、C、D 形式。"""

    return chr(ord("A") + index) if 0 <= index < 26 else str(index)


def actual_changes(parent: dict, variant: dict) -> list[tuple[int, int, float, float]]:
    """直接比较父题和变体，而不是只相信元数据中的修改说明。"""

    changes = []
    for channel, (left, right) in enumerate(zip(parent["series"], variant["series"], strict=True)):
        for time_index, (old, new) in enumerate(zip(left, right, strict=True)):
            if not math.isclose(float(old), float(new), rel_tol=0.0, abs_tol=1e-12):
                changes.append((channel, time_index, float(old), float(new)))
    return changes


def proportional_scale(changes: list[tuple[int, int, float, float]]) -> float | None:
    """若一组改动是统一缩放，返回缩放倍率；否则返回 None。"""

    ratios = [new / old for _channel, _time, old, new in changes if abs(old) > 1e-12]
    if not ratios:
        return None
    reference = ratios[0]
    if all(math.isclose(item, reference, rel_tol=0.0, abs_tol=1e-9) for item in ratios):
        return reference
    return None


def render_change_details(parent: dict, variant: dict) -> list[str]:
    """为交通和风电分别生成易读的改动摘要。"""

    metadata = variant["counterfactual"]
    family = metadata["family"]
    changes = actual_changes(parent, variant)
    lines = [f"- 实际修改数：{len(changes)}"]

    if family == "paired_max_flow":
        lines.append(
            f"- 原最大流量：{number(metadata['original_target'])}；"
            f"修改后最大流量：{number(metadata['counterfactual_target'])}"
        )
        for channel, time_index, old, new in changes:
            speed = float(parent["series"][1][time_index])
            old_flow, new_flow = old * speed, new * speed
            lines.append(
                f"  - t={time_index}：密度 {number(old)} → {number(new)}；"
                f"速度保持 {number(speed)}；流量 {number(old_flow)} → {number(new_flow)}"
            )
        return lines

    # 风电容量因子由功率总和决定。统一缩放时列出倍率和统计量，比列出几十个
    # 时间点更利于人工检查是否超过额定功率。
    old_power, new_power = parent["series"][1], variant["series"][1]
    scale = proportional_scale(changes)
    lines.extend([
        f"- 原容量因子：{number(metadata['original_target'])}%；"
        f"修改后容量因子：{number(metadata['counterfactual_target'])}%",
        f"- 原功率序列：{channel_statistics(old_power)}",
        f"- 新功率序列：{channel_statistics(new_power)}",
    ])
    if scale is not None and len(changes) > 2:
        lines.append(f"- 修改方式：全部非零功率按 {number(scale)} 倍缩放。");
    else:
        for _channel, time_index, old, new in changes:
            wind = float(parent["series"][0][time_index])
            lines.append(
                f"  - t={time_index}：功率 {number(old)} → {number(new)}；"
                f"该时刻风速保持 {number(wind)}"
            )
    return lines


def render_one(index: int, parent: dict, variant: dict) -> str:
    """渲染一条父题—反事实题对，并在 Markdown 中默认折叠。"""

    metadata = variant["counterfactual"]
    kind_cn = {"answer_preserving": "答案保持不变", "answer_changing": "答案应当改变"}[metadata["kind"]]
    parent_choice = metadata["original_expected_choice_index"]
    variant_choice = metadata["expected_choice_index"]
    options = "；".join(f"{option_label(i)}. {value}" for i, value in enumerate(parent["choices"]))
    lines = [
        "<details>",
        f"<summary>样本 {index}：{metadata['family']} / {kind_cn} / {parent['id']}</summary>",
        "",
        f"- 父题ID：`{parent['id']}`",
        f"- 题目：{parent['question'].strip()}",
        f"- 选项：{options}",
        f"- 原题正确项：{option_label(parent_choice)}（数值 {number(metadata['original_target'])}）",
        f"- 变体正确项：{option_label(variant_choice)}（数值 {number(metadata['counterfactual_target'])}）",
        "- 序列字段：" + "；".join(parent["series_names"]),
        *render_change_details(parent, variant),
        "",
        "人工检查：题干和选项未变；修改是否合理；答案保持/改变关系是否符合直觉。",
        "",
        "</details>",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--variants", type=Path, default=DEFAULT_VARIANTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--per-group", type=int, default=5, help="每个任务类型×反事实类型抽取的样本数")
    parser.add_argument("--review-seed", default="manual-review-v1", help="用于稳定抽样的文字种子")
    args = parser.parse_args()
    if args.per_group <= 0:
        raise ValueError("--per-group 必须为正数")

    parents = {row["id"]: row for row in read_jsonl(args.seed)}
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for variant in read_jsonl(args.variants):
        metadata = variant["counterfactual"]
        groups[(metadata["family"], metadata["kind"])].append(variant)

    selected = []
    group_summary = []
    for group in sorted(groups):
        rows = sorted(groups[group], key=lambda row: stable_order_key(row, args.review_seed))
        chosen = rows[:args.per_group]
        selected.extend(chosen)
        group_summary.append((group, len(rows), len(chosen)))
    if not selected:
        raise ValueError("没有可以渲染的反事实样本")

    lines = [
        "# 反事实样本人工审阅包",
        "",
        "这份文件只用于在模型推理前检查生成的数据是否自然。它不包含模型输出，"
        "也不替代程序化公式核验。长序列不全文展开，而是显示改动位置和关键统计量。",
        "",
        f"- 固定抽样种子：`{args.review_seed}`",
        f"- 每组抽取数量：{args.per_group}",
        f"- 合计样本：{len(selected)}",
        "",
        "| 题目类型 | 反事实类型 | 可用样本 | 本次抽取 |",
        "| --- | --- | ---: | ---: |",
    ]
    for (family, kind), available, chosen in group_summary:
        lines.append(f"| {family} | {kind} | {available} | {chosen} |")
    lines.append("")

    for index, variant in enumerate(selected, 1):
        parent = parents.get(variant["parent_id"])
        if parent is None:
            raise ValueError(f"找不到父题：{variant['parent_id']}")
        lines.append(render_one(index, parent, variant))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "samples": len(selected)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
