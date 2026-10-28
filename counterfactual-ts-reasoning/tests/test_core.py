from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cf_ts.choice_parser import parse_choice_index
from cf_ts.core import evaluate, generate_variant, verify_variant


def traffic_row() -> dict:
    return {
        "id": "traffic-demo",
        "task": "numerical_reasoning",
        "question": "Using the relationship Flow (q) = Density (k) × Speed (v), calculate the maximum traffic flow capacity observed during this period. What is this maximum flow value?",
        "choices": ["500.0", "600.0", "700.0", "800.0"],
        "answer_index": 2,
        "series": [[5.0, 6.0, 7.0], [100.0, 100.0, 100.0]],
        "series_names": ["Traffic Density (veh/km)", "Average Speed (km/h)"],
    }


def wind_row() -> dict:
    return {
        "id": "wind-demo",
        "task": "numerical_reasoning",
        "question": "The turbine has rated capacity of 1.5 MW. Calculate the capacity factor (%), defined as total actual energy output divided by rated power times hours.",
        "choices": ["30.0", "35.0", "40.0", "45.0"],
        "answer_index": 2,
        "series": [[5.0, 6.0, 7.0, 8.0], [0.3, 0.6, 0.9, 0.6]],
        "series_names": ["Wind Speed (m/s)", "Power Output (MW)"],
    }


class CounterfactualGenerationTests(unittest.TestCase):
    def test_choice_parser_is_conservative(self) -> None:
        self.assertEqual(parse_choice_index("The answer is C.", 4), 2)
        self.assertEqual(parse_choice_index("答案：B", 4), 1)
        self.assertEqual(parse_choice_index("D. 这是最终答案。", 4), 3)
        self.assertIsNone(parse_choice_index("I cannot determine the answer.", 4))
        self.assertIsNone(parse_choice_index("The answer is Z.", 4))

    def test_traffic_formula_and_variants(self) -> None:
        parent = traffic_row()
        self.assertEqual(evaluate(parent).choice_index, 2)
        for kind, expected_choice in (("answer_preserving", 2), ("answer_changing", 3)):
            variant = generate_variant(parent, kind)
            self.assertEqual(evaluate(variant).choice_index, expected_choice)
            self.assertEqual(verify_variant(parent, variant), [])

    def test_wind_formula_and_variants(self) -> None:
        parent = wind_row()
        self.assertEqual(evaluate(parent).choice_index, 2)
        invariant = generate_variant(parent, "answer_preserving")
        self.assertEqual(evaluate(invariant).choice_index, 2)
        self.assertEqual(verify_variant(parent, invariant), [])

        changing = generate_variant(parent, "answer_changing")
        # 生成器选择满足约束且最接近原值的备选项。这个玩具样本中35%或45%
        # 都是合理结果；关键约束是原本的40%不再是正确答案。
        self.assertNotEqual(evaluate(changing).choice_index, 2)
        self.assertEqual(verify_variant(parent, changing), [])


if __name__ == "__main__":
    unittest.main()
