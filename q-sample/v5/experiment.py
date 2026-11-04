"""先冻结实验矩阵，再运行训练；正式测试由独立的--test阶段触发。"""
import argparse
import hashlib
import json
from pathlib import Path
from train import configuration,run
from evaluate import evaluate,load_model
from data import OfficialDataset
from paths import HERE


def freeze():
    configs=[]
    for seed in (7,11,23):
        for method in ('adaptive','blind','uniform','saliency'):
            regimes=('qa','warmup','joint') if method in ('adaptive','blind') else ('qa',)
            for regime in regimes:
                configs.append(configuration(f'{method}_{regime}_s{seed}',method,regime,seed))
    path=HERE/'experiment_plan.json'
    payload=dict(configs=configs,selection='固定最后一次更新，不以Test选模；训练400步、warmup前100步，总更新数匹配',
                 data_plan_sha256=hashlib.sha256((HERE/'data_plan.json').read_bytes()).hexdigest(),
                 preregistration='文本编码128维；宽48；CNN三尺度；两层Transformer；N128；未用高斯平滑；所有方法同时间协议；density=1、coverage=0；主实验seed7/11/23；小规模探索结果不代表全量benchmark')
    if path.exists():assert json.loads(path.read_text())==payload
    else:path.write_text(json.dumps(payload,ensure_ascii=False,indent=2))
    return configs


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--seed',type=int);parser.add_argument('--test',action='store_true');parser.add_argument('--controls',action='store_true');parser.add_argument('--all',action='store_true');parser.add_argument('--long',action='store_true')
    args=parser.parse_args();configs=freeze()
    if args.controls:
        source='results/adaptive_joint_s7/final.pt'
        configs=[configuration('coordinate_only',control='coordinate',sampler_checkpoint=source,regime='qa'),
                 configuration('query_only',control='query',sampler_checkpoint=source,regime='qa'),
                 configuration('adaptive_joint_signal',time_mode='signal'),configuration('adaptive_joint_gaps',time_mode='gaps'),
                 configuration('adaptive_joint_source_safe',safe_only=True,validation_group='robust_validation')]
        configs += [configuration(f'retention_{method}_s{seed}',method,'warmup',seed,retention_probe=True) for method in ('adaptive','blind') for seed in (7,11,23)]
    if args.long:
        configs=[configuration(f'long_{method}_{n}',method,'joint' if method in ('adaptive','blind') else 'qa',tokens=n,steps=200,warmup_steps=50,train_group='long_train',validation_group='long_validation') for n in (32,64,128,256,512) for method in ('adaptive','blind','uniform','saliency')]
    if args.controls or args.long:
        path=HERE/('control_plan.json' if args.controls else 'long_experiment_plan.json')
        payload=dict(configs=configs,purpose='独立捷径/时间/源安全/预热保持性诊断' if args.controls else '主实验完成后的原生14400点小规模预算试验；不是全量benchmark',frozen_before_test=True)
        if path.exists():assert json.loads(path.read_text())==payload
        else:path.write_text(json.dumps(payload,ensure_ascii=False,indent=2))
    if args.seed is not None:configs=[c for c in configs if c['seed']==args.seed]
    if not(args.seed is not None or args.controls or args.all or args.long):return
    for config in configs:
        folder=HERE/'results'/config['name']
        if args.test:
            if not (folder/'final.pt').exists():continue
            model,_=load_model(folder/'final.pt')
            group='long_test' if args.long else 'robust_test' if config.get('safe_only') else 'test'
            result=evaluate(model,OfficialDataset(group),intervention=config.get('control'))
            (folder/'test.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
            print(config['name'],json.dumps(result['summary']),flush=True)
        else:run(config)


if __name__=='__main__':main()
