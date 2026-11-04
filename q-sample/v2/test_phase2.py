"""第二阶段数据、架构隔离和条件选择指标的正确性测试。"""
import unittest

import numpy as np
import torch

from phase2_data import CLASSES, DataConfig, PairedGenerator, paired_inputs, templates
from phase2_experiment import region_allocation
from phase2_model import Phase2QA


class Phase2Tests(unittest.TestCase):
    def setUp(self):
        self.config = DataConfig(length=32768, event_width=128, noise=0.)

    def test_labels_balanced_and_queries_share_signal(self):
        data = PairedGenerator(self.config, 10).batch(8, 2)
        x, query, labels = paired_inputs(data)
        torch.testing.assert_close(data["labels"].mean(0), torch.full((4,), .5))
        for row in range(8):
            for category in range(len(CLASSES)):
                torch.testing.assert_close(x[row * 4 + category], data["x"][row])
                self.assertEqual(query[row * 4 + category].argmax().item(), category)
                self.assertEqual(labels[row * 4 + category].item(), data["labels"][row, category].item())

    def test_counterfactual_labels_preserve_histogram_and_distractors(self):
        a = PairedGenerator(self.config, 22).batch(4, 2, labels_override=np.zeros((4, 4)))
        b = PairedGenerator(self.config, 22).batch(4, 2, labels_override=np.ones((4, 4)))
        torch.testing.assert_close(a["starts"], b["starts"])
        self.assertEqual(a["all_starts"], b["all_starts"])
        self.assertEqual(a["amplitudes"], b["amplitudes"])
        torch.testing.assert_close(a["x"].sort(dim=1).values, b["x"].sort(dim=1).values)
        for row in range(4):
            for event in range(4, len(a["payloads"][row])):
                np.testing.assert_array_equal(a["payloads"][row][event], b["payloads"][row][event])

    def test_regions_disjoint_and_strong_distractors_larger(self):
        data = PairedGenerator(self.config, 33).batch(4, 2)
        for locations, amplitudes in zip(data["all_starts"], data["amplitudes"]):
            ordered = sorted(locations)
            self.assertTrue(all(b - a >= 1.5 * self.config.event_width for a, b in zip(ordered, ordered[1:])))
            self.assertGreater(min(amplitudes[4:]), max(amplitudes[:4]))
            self.assertTrue(all(0 <= start < self.config.length - self.config.event_width for start in locations))

    def test_noiseless_targets_and_fragmented_controls_differ(self):
        shapes = templates(self.config.event_width)
        data = PairedGenerator(self.config, 44).batch(4, 0, labels_override=np.zeros((4, 4)))
        for row in range(4):
            for category in range(4):
                waveform = data["payloads"][row][category] / data["amplitudes"][row][category]
                np.testing.assert_allclose(np.sort(waveform), np.sort(shapes[category]), atol=1e-6)
                self.assertGreater(np.mean(abs(waveform - shapes[category])), .05)

    def test_query_blind_grid_invariant_and_signal_head_ignores_time(self):
        torch.manual_seed(2)
        model = Phase2QA(tokens=16, coarse=16, width=8, method="query_blind", event_width=128)
        x = torch.randn(1, 201, 1).repeat(4, 1, 1)
        query = torch.eye(4)
        result = model(x, query)
        torch.testing.assert_close(result["grid"], result["grid"][:1].expand(4, -1))
        zero = model.intervene(result, query, "zero")
        changed = model.readout(torch.zeros_like(result["values"]), query, torch.rand_like(result["grid"]))
        torch.testing.assert_close(zero, changed)
        # 同一查询的零信号输出不应依赖原序列或采样几何。
        values = torch.zeros_like(result["values"])
        repeated_query = query[:1].expand(4, -1)
        predictions = model.readout(values, repeated_query)
        torch.testing.assert_close(predictions, predictions[:1].expand(4))

    def test_multiclass_density_receives_qa_gradient(self):
        torch.manual_seed(5)
        model = Phase2QA(tokens=19, coarse=16, width=8)
        result = model(torch.randn(4, 201, 1), torch.eye(4))
        result["logits"].square().mean().backward()
        gradient = model.sampler.density.weight.grad
        self.assertTrue(torch.isfinite(gradient).all())
        self.assertGreater(gradient.abs().sum().item(), 0)

    def test_region_metrics_known_selectivity(self):
        config = DataConfig(length=100000, event_width=384)
        starts = torch.tensor([[1000, 10000, 20000, 30000]])
        grid = ((starts.float() + 100) / (config.length - 1)).reshape(4, 1).expand(4, 8)
        result = {"grid": grid, "mass": torch.ones(4, config.length) / config.length}
        data = {"labels": torch.ones(1, 4), "starts": starts, "all_starts": starts.tolist()}
        occupancy, counts, mass, extra, _, _ = region_allocation(result, data, config)
        torch.testing.assert_close(occupancy[0], torch.eye(4))
        self.assertTrue((counts.diagonal(dim1=1, dim2=2) == 8).all())
        torch.testing.assert_close(mass, torch.full((1, 4, 4), 384 / 100000, dtype=torch.double))
        torch.testing.assert_close(extra, torch.zeros_like(extra))

    def test_oracle_has_no_role_in_main_path(self):
        model = Phase2QA(tokens=8, coarse=16, width=8)
        x, query = torch.randn(4, 201, 1), torch.eye(4)
        a = model(x, query)
        b = model(x, query, oracle_starts=torch.tensor([0, 20, 40, 60]))
        torch.testing.assert_close(a["logits"], b["logits"])


if __name__ == "__main__":
    unittest.main()
