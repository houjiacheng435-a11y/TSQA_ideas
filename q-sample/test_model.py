import unittest

import torch
from torch.autograd import gradcheck
from torch.nn import functional as F

from model import QSample, SyntheticQA, gaussian_smooth, inverse_cdf, sample_linear


class SamplingTests(unittest.TestCase):
    def test_uniform_quantiles_and_endpoints(self):
        mass = torch.ones(2, 100, dtype=torch.double)
        grid = inverse_cdf(mass, 10)
        expected = (torch.arange(10, dtype=torch.double) + 0.5) / 10
        torch.testing.assert_close(grid, expected.expand(2, -1))
        x = torch.arange(7, dtype=torch.double).view(1, 7, 1)
        got = sample_linear(x, torch.tensor([[0., 0.25, 1.]], dtype=torch.double))
        torch.testing.assert_close(got.flatten(), torch.tensor([0., 1.5, 6.], dtype=torch.double))

    def test_inverse_and_sampling_gradients(self):
        mass = torch.tensor([[.13, .21, .29, .37]], dtype=torch.double, requires_grad=True)
        self.assertTrue(gradcheck(lambda p: inverse_cdf(p, 5), (mass,)))
        x = torch.tensor([[[0.], [2.], [1.], [4.]]], dtype=torch.double, requires_grad=True)
        grid = torch.tensor([[.11, .47, .91]], dtype=torch.double, requires_grad=True)
        self.assertTrue(gradcheck(sample_linear, (x, grid)))
        self.assertTrue(gradcheck(lambda p: sample_linear(x, inverse_cdf(p, 5)), (mass,)))

    def test_extreme_density_floor(self):
        mass = torch.full((1, 100000), 1e-9, dtype=torch.double)
        mass[0, 50000] += 1 - 1e-4
        grid = inverse_cdf(mass, 512)
        self.assertTrue(torch.isfinite(grid).all())
        self.assertTrue((grid.diff() >= 0).all())
        self.assertTrue(((grid >= 0) & (grid <= 1)).all())

    def test_fft_matches_direct_convolution(self):
        torch.manual_seed(1)
        x = torch.randn(2, 31, 2, dtype=torch.double)
        sigma = 1.5
        radius = 5
        t = torch.arange(-radius, radius + 1, dtype=x.dtype)
        kernel = torch.exp(-0.5 * (t / sigma).square())
        kernel = (kernel / kernel.sum()).view(1, 1, -1).expand(2, 1, -1)
        direct = F.conv1d(F.pad(x.transpose(1, 2), (radius, radius), mode="replicate"),
                          kernel, groups=2).transpose(1, 2)
        torch.testing.assert_close(gaussian_smooth(x, sigma), direct)

    def test_density_receives_task_gradient(self):
        torch.manual_seed(8)
        sampler = QSample(coarse=16, tokens=19, width=8).double()
        x = torch.randn(2, 201, 1, dtype=torch.double)
        query = torch.tensor([[1.], [-1.]], dtype=torch.double)
        result = sampler(x, query)
        result["values"].square().mean().backward()
        gradient = sampler.density.weight.grad
        self.assertTrue(torch.isfinite(gradient).all())
        self.assertGreater(gradient.abs().sum().item(), 0)
        torch.testing.assert_close(result["mass"].sum(-1), torch.ones(2, dtype=torch.double))

    def test_flat_signal_has_no_coordinate_gradient(self):
        grid = torch.tensor([[.15, .65]], requires_grad=True)
        sample_linear(torch.ones(1, 20, 1), grid).sum().backward()
        torch.testing.assert_close(grid.grad, torch.zeros_like(grid))

    def test_reject_invalid_mass(self):
        for mass in (torch.zeros(1, 3), torch.tensor([[1., float("nan")]])):
            with self.assertRaises(ValueError):
                inverse_cdf(mass, 4)

    def test_query_blind_control_and_value_ablation(self):
        torch.manual_seed(2)
        model = SyntheticQA(coarse=8, tokens=11, width=8)
        x = torch.randn(2, 71, 1)
        query = torch.tensor([[1.], [-1.]])
        a = model(x, query, mode="adaptive_query_blind")
        b = model(x, -query, mode="adaptive_query_blind")
        torch.testing.assert_close(a["grid"], b["grid"])
        # Signal-only readout cannot recover an answer from grid geometry.
        zero = model(x, query, value_mode="zero")
        torch.testing.assert_close(zero["logits"], zero["logits"][0].expand(2))


if __name__ == "__main__":
    unittest.main()
