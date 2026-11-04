"""完成主矩阵和捷径诊断后，才运行原生长输入的小规模预算试验。"""
import subprocess
import sys
import time
import json
from data import groups,signal_path
from paths import HERE
from diagnose import plots


def wait(predicate,label):
    started=time.time()
    while not predicate():
        if time.time()-started>3600:raise TimeoutError(label)
        print('等待'+label,flush=True);time.sleep(20)


if __name__=='__main__':
    wait(lambda:(HERE/'results/main_table.md').exists(),'Stage3完整正式评分与控制')
    for group in ('long_train','long_validation','long_test'):
        wait(lambda:all(signal_path(r).exists() for r in groups()[group]),group)
    subprocess.run([sys.executable,'experiment.py','--long'],check=True)
    subprocess.run([sys.executable,'experiment.py','--long','--test'],check=True)
    for path in sorted((HERE/'results').glob('long_*/final.pt')):plots(path,'long_test')
    subprocess.run([sys.executable,'summarize.py'],check=True)
    (HERE/'results/long_complete.json').write_text(json.dumps(dict(status='completed',runs=20,train_n=16,validation_n=8,test_n=8,seed=7,tokens=[32,64,128,256,512]),indent=2))
