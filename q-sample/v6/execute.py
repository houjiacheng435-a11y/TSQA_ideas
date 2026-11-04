"""先完成固定32题拟合，再使用1024道Train题；所有方法使用最后一步模型。"""
import json
import time
from dataset import path
from legacy import HERE
from run import CASES,train,summarize
from tests import main as tests

if __name__=='__main__':
    tests()
    for case in CASES:train(case,'overfit',1000);summarize()
    groups=json.loads((HERE/'data_plan.json').read_text())['groups']
    started=time.time()
    while not all(path(r).exists() for key in ('train','validation') for r in groups[key]):
        missing=sum(not path(r).exists() for key in ('train','validation') for r in groups[key])
        print('等待固定Train/Validation窗口',missing,flush=True)
        if time.time()-started>7200:raise TimeoutError('不能替换失败窗口')
        time.sleep(20)
    for case in CASES:train(case,'main',2000);summarize()
