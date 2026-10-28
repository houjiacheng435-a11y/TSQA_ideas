"""从模型回复中保守地提取多选题选项。"""
from __future__ import annotations

import re


_EXPLICIT_LABEL = re.compile(
    r"(?:answer|option|choice|答案|选项)\s*(?:is|为|是|:|：|=)?\s*[\(\[]?([A-Za-z])\b",
    re.IGNORECASE,
)
_LEADING_LABEL = re.compile(r"^\s*(?:答案\s*[是为:]?\s*)?[\(\[]?([A-Za-z])(?:[\)\]\.、:：\s]|$)")


def parse_choice_index(text: str, choice_count: int) -> int | None:
    """提取回复中明确给出的 A/B/C/... 选项下标。

    只有回复明确说出 ``answer is B``、``答案：B``，或以 ``B.`` 开头时才
    返回下标。无法确定时返回 ``None``，而不是猜测，以便后续单独统计解析
    失败的回复。
    """

    if choice_count < 1 or not text:
        return None
    matches = _EXPLICIT_LABEL.findall(text)
    if matches:
        label = matches[-1].upper()
        index = ord(label) - ord("A")
        return index if 0 <= index < choice_count else None
    for line in text.splitlines():
        match = _LEADING_LABEL.match(line)
        if match:
            label = match.group(1).upper()
            index = ord(label) - ord("A")
            return index if 0 <= index < choice_count else None
    return None
