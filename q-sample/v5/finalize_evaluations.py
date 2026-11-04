"""冻结方案后的最终验证/测试与诊断，绝不更新模型参数。"""
import argparse
import json
from pathlib import Path

from data import OfficialDataset
from evaluate import evaluate,load_model
from experiment import freeze
from diagnose import diagnostics,plots
from paths import HERE


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--diagnostics',action='store_true');parser.add_argument('--plots',action='store_true');args=parser.parse_args()
    folders=sorted(p.parent for p in (HERE/'results').glob('*/final.pt') if p.parent.name!='overfit32')
    for folder in folders:
        model,config=load_model(folder/'final.pt')
        for split in ('validation','test'):
            group='long_'+split if config.get('train_group')=='long_train' else 'robust_'+split if config.get('safe_only') else split
            output=evaluate(model,OfficialDataset(group),intervention=config.get('control'))
            (folder/f'{split}.json').write_text(json.dumps(output,ensure_ascii=False,indent=2))
        print(folder.name,'最终验证/测试完成',flush=True)
        if args.plots and not config.get('control'):plots(folder/'final.pt','long_test' if config.get('train_group')=='long_train' else 'robust_test' if config.get('safe_only') else 'test')
        if args.diagnostics and folder.name in ('adaptive_qa_s7','adaptive_warmup_s7','adaptive_joint_s7','blind_joint_s7','uniform_qa_s7'):
            diagnostics(folder/'final.pt','test')


if __name__=='__main__':main()
