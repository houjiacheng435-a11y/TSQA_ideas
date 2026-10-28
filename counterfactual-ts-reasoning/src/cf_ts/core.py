"""公式计算、反事实生成和独立核验。

这里有意只支持两类带显式公式的 TSRBench 题目。范围保持较小，才能让
每一条生成的标签都能被重新计算和检查：

* paired_max_flow：max_t(密度_t * 速度_t)
* wind_capacity_factor：sum_t(功率_t) / (额定功率 * 时长) * 100

生成反事实标签时绝不采用原基准自带的 ``answer_index``，而是重新计算数
值目标，并在显示选项中寻找唯一匹配项。
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Callable


TRAFFIC_FAMILY = "paired_max_flow"
WIND_FAMILY = "wind_capacity_factor"


class CounterfactualError(ValueError):
    """当题目无法安全地得到程序化标签时抛出。"""


@dataclass(frozen=True)
class Evaluation:
    """重新计算出的数值目标及其唯一匹配的显示选项。"""

    family: str
    target: float
    choice_index: int
    matching_choice_indices: tuple[int, ...]


def canonical_sha256(value: Any) -> str:
    """为生成 JSONL 中的溯源字段返回稳定的哈希值。"""

    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def detect_family(question: str) -> str:
    """识别题目是否属于当前支持的两类公式题之一。"""

    lowered = question.lower()
    if "maximum traffic flow capacity" in lowered:
        return TRAFFIC_FAMILY
    if "capacity factor" in lowered and "rated capacity" in lowered:
        return WIND_FAMILY
    raise CounterfactualError("Question is outside the supported formula families")


def _aligned_channels(row: dict[str, Any], expected_channels: int) -> list[list[float]]:
    """读取有限、等长的数值序列，并尽早拒绝格式异常的输入。"""

    raw_channels = row.get("series")
    if not isinstance(raw_channels, list) or len(raw_channels) != expected_channels:
        raise CounterfactualError(f"Expected {expected_channels} series channels")
    channels = [[float(value) for value in channel] for channel in raw_channels]
    if not channels or not channels[0] or len({len(channel) for channel in channels}) != 1:
        raise CounterfactualError("Series channels must be non-empty and aligned")
    if not all(math.isfinite(value) for channel in channels for value in channel):
        raise CounterfactualError("Series contains a non-finite number")
    return channels


def rated_capacity(question: str) -> float:
    """从固定题目模板中提取风机额定功率。"""

    match = re.search(r"rated capacity of\s+([\d.]+)\s+MW", question, re.IGNORECASE)
    if match is None:
        raise CounterfactualError("Could not find rated capacity in wind question")
    capacity = float(match.group(1))
    if not math.isfinite(capacity) or capacity <= 0:
        raise CounterfactualError("Rated capacity must be positive")
    return capacity


def _decimal_tolerance(choice: Any) -> float:
    """按原项目的显示精度规则计算容差。

    数值目标必须落在选项最后一位小数的一半范围内，避免把仅仅接近的
    四舍五入数误判为精确答案。
    """

    text = str(choice).strip()
    if not re.fullmatch(r"[-+]?\d+(?:\.\d+)?", text):
        raise CounterfactualError(f"Choice is not a decimal number: {choice!r}")
    places = len(text.split(".", 1)[1]) if "." in text else 0
    return 0.5 * 10 ** (-places) + 1e-6


def matching_choice_indices(choices: list[Any], target: float) -> tuple[int, ...]:
    """返回显示数值与 ``target`` 匹配的全部选项下标。"""

    matches = []
    for index, choice in enumerate(choices):
        value = float(choice)
        if not math.isfinite(value):
            raise CounterfactualError("Choice is non-finite")
        if abs(value - target) <= _decimal_tolerance(choice):
            matches.append(index)
    return tuple(matches)


def evaluate(row: dict[str, Any]) -> Evaluation:
    """重新计算题目的目标值，并要求恰好存在一个有效选项。"""

    question = str(row.get("question", ""))
    family = detect_family(question)
    if family == TRAFFIC_FAMILY:
        density, speed = _aligned_channels(row, expected_channels=2)
        target = max(density_value * speed_value for density_value, speed_value in zip(density, speed, strict=True))
    else:
        _wind, power = _aligned_channels(row, expected_channels=2)
        capacity = rated_capacity(question)
        target = sum(power) / (capacity * len(power)) * 100.0

    choices = row.get("choices")
    if not isinstance(choices, list) or len(choices) < 2:
        raise CounterfactualError("Expected at least two numeric choices")
    matches = matching_choice_indices(choices, target)
    if len(matches) != 1:
        raise CounterfactualError(
            f"Target {target:.10g} must match exactly one displayed choice; found {matches}"
        )
    return Evaluation(family=family, target=target, choice_index=matches[0], matching_choice_indices=matches)


def _changed_entry(channel: int, time_index: int, old: float, new: float) -> dict[str, float | int]:
    return {"channel": channel, "time_index": time_index, "old": old, "new": new}


def _traffic_invariant(row: dict[str, Any], before: Evaluation) -> tuple[dict[str, Any], list[dict[str, float | int]]]:
    """修改非最大流量时刻，同时保持最大流量不变。"""

    modified = copy.deepcopy(row)
    density, speed = _aligned_channels(modified, expected_channels=2)
    flows = [left * right for left, right in zip(density, speed, strict=True)]
    maximum = max(flows)
    # 优先选择可以上调10%的点：既让修改足够明显，又能证明它仍不会成为最大值。
    for index, (density_value, speed_value, flow) in enumerate(zip(density, speed, flows, strict=True)):
        if density_value > 0 and flow * 1.1 < maximum - 1e-8:
            new_density = density_value * 1.1
            modified["series"][0][index] = new_density
            return modified, [_changed_entry(0, index, density_value, new_density)]
    # 若所有非最大值都接近最大值，则降低其中一个正密度值；按构造答案仍不变。
    for index, (density_value, flow) in enumerate(zip(density, flows, strict=True)):
        if density_value > 0 and flow < maximum - 1e-8:
            new_density = density_value * 0.9
            modified["series"][0][index] = new_density
            return modified, [_changed_entry(0, index, density_value, new_density)]
    raise CounterfactualError("No safely non-maximum traffic point available")


def _traffic_decisive(row: dict[str, Any], before: Evaluation) -> tuple[dict[str, Any], list[dict[str, float | int]]]:
    """改变决定性交通峰值，使另一个原有选项成为新的最大值。

    TSRBench 中接近正确值的干扰选项通常比原最大值更小。此时只降低原峰值
    会使另一个接近峰值的点露出来。因此把不低于新目标的小部分点一并降低，
    但保留一个锚点恰好等于新目标。修改最多涉及12个点，且不改变题干或选项。
    """

    modified = copy.deepcopy(row)
    density, speed = _aligned_channels(modified, expected_channels=2)
    flows = [left * right for left, right in zip(density, speed, strict=True)]
    maximum = max(flows)
    maximum_indices = [index for index, value in enumerate(flows)
                       if math.isclose(value, maximum, rel_tol=0.0, abs_tol=1e-9)]
    maximum_index = maximum_indices[0]
    candidates: list[tuple[float, int, float, list[tuple[int, float]]]] = []
    for choice_index, choice in enumerate(row["choices"]):
        if choice_index == before.choice_index:
            continue
        candidate = float(choice)
        ratio = candidate / maximum if maximum else math.inf
        if candidate <= 0 or not 0.5 <= ratio <= 1.5:
            continue
        proposed: list[tuple[int, float]] = []
        feasible = True
        for index, flow in enumerate(flows):
            if index == maximum_index:
                desired_flow = candidate
            elif flow >= candidate:
                # 把所有竞争点压到目标值以下。微小间隔保证新最大值唯一，
                # 同时不改变目标值本身，也不修改显示选项。
                desired_flow = candidate * (1.0 - 1e-6)
            else:
                continue
            if speed[index] <= 0:
                feasible = False
                break
            new_density = desired_flow / speed[index]
            density_ratio = new_density / density[index] if density[index] else math.inf
            if not math.isfinite(new_density) or new_density <= 0 or not 0.5 <= density_ratio <= 1.5:
                feasible = False
                break
            proposed.append((index, new_density))
        if feasible and 1 <= len(proposed) <= 12:
            candidates.append((abs(ratio - 1.0), choice_index, candidate, proposed))
    if not candidates:
        raise CounterfactualError("No bounded existing traffic option can become the new unique maximum")

    _distance, choice_index, _target, proposed = min(candidates)
    changes = []
    for index, new_density in proposed:
        old_density = density[index]
        modified["series"][0][index] = new_density
        changes.append(_changed_entry(0, index, old_density, new_density))
    after = evaluate(modified)
    if after.choice_index != choice_index:
        raise CounterfactualError("Traffic intervention did not produce the selected existing option")
    return modified, changes


def _wind_invariant(row: dict[str, Any], before: Evaluation) -> tuple[dict[str, Any], list[dict[str, float | int]]]:
    """在两个小时之间转移少量功率，但保持总和不变。

    容量因子只取决于总发电量，不取决于功率出现在哪个小时。选择风速最接近
    的两个时刻，并把功率限制在 [0, 额定功率] 内，避免无必要的不合理修改。
    """

    modified = copy.deepcopy(row)
    wind, power = _aligned_channels(modified, expected_channels=2)
    capacity = rated_capacity(modified["question"])
    candidates: list[tuple[float, int, int, float]] = []
    for source_index, source_power in enumerate(power):
        if source_power <= 1e-9:
            continue
        for destination_index, destination_power in enumerate(power):
            if source_index == destination_index or destination_power >= capacity - 1e-9:
                continue
            delta = min(0.05 * capacity, source_power / 3.0, (capacity - destination_power) / 3.0)
            if delta > 1e-9:
                candidates.append((abs(wind[source_index] - wind[destination_index]), source_index, destination_index, delta))
    if not candidates:
        raise CounterfactualError("No bounded pair available for sum-preserving wind edit")
    _difference, source_index, destination_index, delta = min(candidates)
    old_source, old_destination = power[source_index], power[destination_index]
    modified["series"][1][source_index] = old_source - delta
    modified["series"][1][destination_index] = old_destination + delta
    return modified, [
        _changed_entry(1, source_index, old_source, old_source - delta),
        _changed_entry(1, destination_index, old_destination, old_destination + delta),
    ]


def _wind_decisive(row: dict[str, Any], before: Evaluation) -> tuple[dict[str, Any], list[dict[str, float | int]]]:
    """按比例缩放观测功率，使容量因子变为另一个原有选项。"""

    modified = copy.deepcopy(row)
    _wind, power = _aligned_channels(modified, expected_channels=2)
    capacity = rated_capacity(modified["question"])
    candidates: list[tuple[float, int, float]] = []
    for choice_index, choice in enumerate(row["choices"]):
        if choice_index == before.choice_index:
            continue
        requested_target = float(choice)
        scale = requested_target / before.target if before.target else math.inf
        # 仅允许50%--150%的缩放，是第一轮实验中较保守的合理性约束。
        if 0.5 <= scale <= 1.5 and all(value * scale <= capacity + 1e-9 for value in power):
            candidates.append((abs(scale - 1.0), choice_index, scale))
    if not candidates:
        raise CounterfactualError("No bounded existing wind option can be reached by power scaling")
    _distance, choice_index, scale = min(candidates)
    changes = []
    for index, old_power in enumerate(power):
        new_power = old_power * scale
        if not math.isclose(old_power, new_power, rel_tol=0.0, abs_tol=1e-12):
            modified["series"][1][index] = new_power
            changes.append(_changed_entry(1, index, old_power, new_power))
    after = evaluate(modified)
    if after.choice_index != choice_index:
        raise CounterfactualError("Wind intervention did not produce the selected existing option")
    return modified, changes


_TRANSFORMS: dict[tuple[str, str], Callable[[dict[str, Any], Evaluation], tuple[dict[str, Any], list[dict[str, float | int]]]]] = {
    (TRAFFIC_FAMILY, "answer_preserving"): _traffic_invariant,
    (TRAFFIC_FAMILY, "answer_changing"): _traffic_decisive,
    (WIND_FAMILY, "answer_preserving"): _wind_invariant,
    (WIND_FAMILY, "answer_changing"): _wind_decisive,
}


def generate_variant(parent: dict[str, Any], kind: str) -> dict[str, Any]:
    """生成一条自带修改说明、且经过公式检查的反事实题。"""

    before = evaluate(parent)
    try:
        transform = _TRANSFORMS[(before.family, kind)]
    except KeyError as exc:
        raise CounterfactualError(f"Unsupported counterfactual kind {kind!r}") from exc
    modified, changes = transform(parent, before)
    after = evaluate(modified)

    if kind == "answer_preserving":
        if after.choice_index != before.choice_index or not math.isclose(after.target, before.target, rel_tol=0.0, abs_tol=1e-7):
            raise CounterfactualError("Answer-preserving variant changed its recomputed answer")
    elif kind == "answer_changing":
        if after.choice_index == before.choice_index:
            raise CounterfactualError("Answer-changing variant retained its original choice")
    else:
        raise CounterfactualError(f"Unknown kind: {kind}")

    parent_id = str(parent.get("id"))
    if not parent_id:
        raise CounterfactualError("Parent row has no id")
    variant = modified
    variant["id"] = f"cf-{kind}--{parent_id}"
    variant["parent_id"] = parent_id
    variant["dataset_answer_index"] = parent.get("dataset_answer_index", parent.get("answer_index"))
    variant["answer_index"] = after.choice_index
    variant["counterfactual"] = {
        "family": before.family,
        "kind": kind,
        "parent_series_sha256": canonical_sha256(parent["series"]),
        "original_target": before.target,
        "counterfactual_target": after.target,
        "original_expected_choice_index": before.choice_index,
        "expected_choice_index": after.choice_index,
        "changed_positions": changes,
    }
    return variant


def verify_variant(parent: dict[str, Any], variant: dict[str, Any]) -> list[str]:
    """独立检查生成题是否满足其声明的反事实关系。"""

    errors: list[str] = []
    metadata = variant.get("counterfactual")
    if not isinstance(metadata, dict):
        return ["missing counterfactual metadata"]
    if variant.get("parent_id") != parent.get("id"):
        errors.append("parent_id does not match parent row")
    for field in ("question", "choices", "series_names"):
        if variant.get(field) != parent.get(field):
            errors.append(f"{field} changed, but it must remain fixed")
    if canonical_sha256(parent.get("series")) != metadata.get("parent_series_sha256"):
        errors.append("parent series hash mismatch")

    try:
        before = evaluate(parent)
        after = evaluate(variant)
    except CounterfactualError as exc:
        return errors + [str(exc)]

    if metadata.get("family") != before.family or after.family != before.family:
        errors.append("family metadata or family evaluation mismatch")
    if variant.get("answer_index") != after.choice_index:
        errors.append("stored answer_index does not match recomputed choice")
    if metadata.get("expected_choice_index") != after.choice_index:
        errors.append("metadata expected choice does not match recomputed choice")
    if metadata.get("original_expected_choice_index") != before.choice_index:
        errors.append("metadata original choice does not match parent recomputation")
    if not math.isclose(float(metadata.get("original_target", math.nan)), before.target, rel_tol=0.0, abs_tol=1e-7):
        errors.append("metadata original target does not match parent recomputation")
    if not math.isclose(float(metadata.get("counterfactual_target", math.nan)), after.target, rel_tol=0.0, abs_tol=1e-7):
        errors.append("metadata counterfactual target does not match variant recomputation")

    kind = metadata.get("kind")
    if kind == "answer_preserving":
        if before.choice_index != after.choice_index or not math.isclose(before.target, after.target, rel_tol=0.0, abs_tol=1e-7):
            errors.append("answer-preserving relation failed")
    elif kind == "answer_changing":
        if before.choice_index == after.choice_index:
            errors.append("answer-changing relation failed")
    else:
        errors.append("unknown counterfactual kind")

    declared = metadata.get("changed_positions")
    if not isinstance(declared, list) or not declared:
        errors.append("no changed positions were recorded")
    else:
        actual_changes = set()
        for channel, (parent_channel, variant_channel) in enumerate(zip(parent["series"], variant["series"], strict=True)):
            for time_index, (old, new) in enumerate(zip(parent_channel, variant_channel, strict=True)):
                if not math.isclose(float(old), float(new), rel_tol=0.0, abs_tol=1e-12):
                    actual_changes.add((channel, time_index))
        declared_changes = {(entry.get("channel"), entry.get("time_index")) for entry in declared if isinstance(entry, dict)}
        if actual_changes != declared_changes:
            errors.append("declared changed positions do not equal actual series changes")
    return errors
