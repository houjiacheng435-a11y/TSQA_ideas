"""数值组件测试与真实官方样本工程测试；随机张量不作为QA性能结果。"""
import json
import unittest
import torch
from torch.utils.data import DataLoader

from model import QSample,inverse_cdf,sample_linear
from losses import qa_loss,density_loss
from data import OfficialDataset,collate,to_device,parse_span,serialize_span,official_scorer
from paths import HERE


class Components(unittest.TestCase):
    def setUp(self):torch.manual_seed(7);torch.set_num_threads(2)

    def test_uniform_and_edges(self):
        for n in (32,64,128,256,512):
            p=torch.ones(2,14400)/14400
            grid=inverse_cdf(p,n,torch.tensor([14400,14400]))
            self.assertTrue(torch.allclose(grid[0],(torch.arange(n)+.5)/n,atol=2e-6))
            self.assertTrue((grid[:,1:]>=grid[:,:-1]).all());self.assertTrue(((grid>=0)&(grid<=1)).all())
        p=torch.tensor([[1e-20,1e-20,1.,1e-20]],requires_grad=True)
        grid=inverse_cdf(p,512,torch.tensor([4]));grid.sum().backward()
        self.assertTrue(torch.isfinite(p.grad).all());self.assertTrue(torch.isfinite(grid).all())
        self.assertLess(float(grid.max()-grid.min()),.251)

    def test_padding_and_interpolation(self):
        p=torch.tensor([[.25,.25,.25,.25,0,0]])
        grid=inverse_cdf(p,4,torch.tensor([4]))
        x=torch.tensor([[[0.],[1.],[2.],[3.],[999.],[999.]]])
        self.assertTrue(torch.allclose(sample_linear(x,grid,torch.tensor([4]))[0,:,0],torch.tensor([.375,1.125,1.875,2.625])))
        model=QSample(tokens=32).eval();q=torch.randn(1,128)
        a=model.distribution(x[:,:4],torch.tensor([4]),q)
        b=model.distribution(x,torch.tensor([4]),q)
        self.assertTrue(torch.allclose(a,b[:,:4]));self.assertEqual(float(b[:,4:].sum()),0)

    def test_gradient_and_finite_difference(self):
        p=torch.tensor([[.17,.23,.29,.31]],requires_grad=True)
        y=inverse_cdf(p,3,torch.tensor([4])).square().sum();y.backward()
        step=1e-3;delta=torch.zeros_like(p);delta[0,1]=step
        finite=(inverse_cdf(p.detach()+delta,3,torch.tensor([4])).square().sum()-inverse_cdf(p.detach()-delta,3,torch.tensor([4])).square().sum())/(2*step)
        self.assertAlmostEqual(float(p.grad[0,1]),float(finite),places=3)
        model=QSample(tokens=32,time_mode='signal')
        x=torch.randn(2,150,1)*1000
        result=model(x,torch.tensor([150,150]),torch.tensor([6.,6.]),torch.randn(2,128))
        loss=result['output']['existence'].square().mean();loss.backward()
        norm=sum(float(v.grad.abs().sum()) for v in model.density.parameters() if v.grad is not None)
        self.assertGreater(norm,0);self.assertTrue(torch.isfinite(torch.tensor(norm)))

    def test_readout_isolation_and_query_blind(self):
        model=QSample(tokens=32,method='blind',time_mode='signal').eval()
        x=torch.randn(1,150,1);length=torch.tensor([150]);q=torch.randn(1,128)
        p=model.distribution(x,length,q)
        pp=model.distribution(x,length,q+10)
        self.assertTrue(torch.equal(p,pp))
        values=torch.zeros(1,32,1);a=torch.linspace(.01,.99,32)[None];b=a.square()
        first=model.readout(values,a,length,torch.tensor([6.]),q)
        second=model.readout(values,b,length,torch.tensor([6.]),q)
        self.assertTrue(torch.allclose(first['localization'],second['localization']))
        self.assertTrue(torch.allclose(first['existence'],second['existence']))

    def test_real_smoke(self):
        loader=DataLoader(OfficialDataset('smoke'),batch_size=2,collate_fn=collate)
        model=QSample(tokens=128).cuda();results=[];evaluate=official_scorer()
        for batch in loader:
            moved=to_device(batch,'cuda');out=model(**moved['inputs'])
            qa,_=qa_loss(out['output'],moved['targets'],moved['inputs']['lengths'])
            kl=density_loss(out['p'],moved['targets'],moved['inputs']['lengths'])
            grad=torch.autograd.grad(qa,list(model.density.parameters()),allow_unused=True,retain_graph=True)
            norm=sum(float(g.abs().sum()) for g in grad if g is not None)
            self.assertTrue(torch.isfinite(qa+kl));self.assertGreater(norm,0)
            self.assertTrue(torch.allclose(out['p'].sum(-1),torch.ones(2,device='cuda'),atol=1e-5))
            for row in batch['rows']:
                self.assertTrue(evaluate(row['answer'],row['answer'],row['answer_type'])['correct'])
                if row['task_type']=='localization':
                    pair=parse_span(row['answer']);encoded=serialize_span([t/row['context_length_s'] for t in pair],row['context_length_s'])
                    self.assertEqual(encoded,row['answer'])
            (qa+kl).backward();results.append(dict(lengths=moved['inputs']['lengths'].tolist(),qa=float(qa),kl=float(kl),qa_density_grad_l1=norm))
        (HERE/'results/smoke.json').write_text(json.dumps(results,indent=2))


if __name__=='__main__':unittest.main(verbosity=2)
