"""按工程测试→过拟合→主实验顺序执行；网络等待不改变固定样本清单。"""
import json
import subprocess
import sys
import time
from pathlib import Path
from data import groups,signal_path
from paths import HERE
from train import run,configuration
from experiment import freeze


def wait_group(name):
    start=time.time()
    while True:
        missing=[r['row_id'] for r in groups()[name] if not signal_path(r).exists()]
        if not missing:return
        print(f'等待{name}：缺{len(missing)}个固定窗口',flush=True)
        if time.time()-start>3600:raise TimeoutError(missing)
        time.sleep(20)


if __name__=='__main__':
    wait_group('smoke')
    with (HERE/'results/tests.log').open('w') as log:subprocess.run([sys.executable,'-m','unittest','tests','-v'],stdout=log,stderr=subprocess.STDOUT,check=True)
    wait_group('overfit')
    run(configuration('overfit32',steps=800,train_group='overfit',validation_group='overfit',eval_every=200))
    wait_group('train')
    # 不用过拟合或验证结果改变冻结的主实验矩阵。
    for config in freeze():run(config)
