"""先验证真实输入、无旁路边界和Pointer表达能力，再开始正式训练。"""
import json
import torch
from dataset import Dataset,semantics,DEVICES
from network import Model,losses
from run import maximum_iou
from legacy import HERE


def main():
    torch.set_num_threads(4);torch.manual_seed(7);data=Dataset('overfit');records=[]
    for method in ('full','oracle','uniform','adaptive','blind'):
        for head in ('regression','pointer'):
            model=Model(method,head).cuda()
            inputs,labels,_=data.batch([0,1])
            kwargs=dict(oracle_grid=labels['oracle']) if method=='oracle' else {}
            output=model(**inputs,**kwargs)
            loss,_=losses(output,labels['span'],inputs['lengths'],labels['proxy'],method in ('adaptive','blind'))
            if method=='adaptive':
                qa,_=losses(output,labels['span'],inputs['lengths'],labels['proxy'],False)
                grads=torch.autograd.grad(qa,list(model.sampler.density.parameters()),retain_graph=True,allow_unused=True)
                assert any(g is not None and g.abs().sum()>0 for g in grads)
            loss.backward();assert torch.isfinite(loss)
            assert (output['span'][:,0]<=output['span'][:,1]).all()
            if method=='adaptive':assert any(p.grad is not None and p.grad.abs().sum()>0 for p in model.sampler.density.parameters())
            if method not in ('full','oracle'):
                try:model(**inputs,oracle_grid=labels['oracle'])
                except ValueError:pass
                else:raise AssertionError('学习模型意外接受Oracle输入')
            records.append(dict(method=method,head=head,loss=float(loss)))
    # 完整6秒网格必须能精确表示官方样本边界；这与稀疏网格上界有本质区别。
    for item in data.items:
        length=len(item['x']);a,b=(item['span']*length).tolist()
        assert abs(a-round(a))<.001 and abs(b-round(b))<.001
    (HERE/'results/tests.json').write_text(json.dumps(records,indent=2));print('10种真实前向/反传、Oracle隔离与原生边界检查通过')


if __name__=='__main__':main()
