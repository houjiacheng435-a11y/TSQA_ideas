"""主矩阵完成后运行独立控制；全部固定窗口补齐后统一正式评测。"""
import subprocess
import sys
import time
from data import groups,signal_path
from experiment import freeze
from paths import HERE


def wait(predicate,label):
    started=time.time()
    while not predicate():
        if time.time()-started>3600:raise TimeoutError(label)
        print('等待'+label,flush=True);time.sleep(20)


if __name__=='__main__':
    wait(lambda:all((HERE/'results'/c['name']/'final.pt').exists() for c in freeze()),'主矩阵24个最终checkpoint')
    subprocess.run([sys.executable,'experiment.py','--controls'],check=True)
    for group in ('validation','test','robust_validation','robust_test'):
        wait(lambda:all(signal_path(r).exists() for r in groups()[group]),group+'全部固定窗口')
    subprocess.run([sys.executable,'finalize_evaluations.py','--diagnostics','--plots'],check=True)
    subprocess.run([sys.executable,'audit_inputs.py'],check=True)
    subprocess.run([sys.executable,'summarize.py'],check=True)
