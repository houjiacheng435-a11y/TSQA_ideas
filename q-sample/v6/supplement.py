"""主矩阵完成后补充粗格Oracle与去硬截断对照，不替换原失败结果。"""
import time
from legacy import HERE
from run import CASES,case_name,train,summarize

if __name__=='__main__':
    started=time.time()
    while not all((HERE/'results'/('main_'+case_name(case)+'.json')).exists() for case in CASES[:13]):
        if time.time()-started>7200:raise TimeoutError('主矩阵未完成')
        time.sleep(20)
    for stage,steps in [('overfit',1000),('main',2000)]:
        for case in CASES[13:]:train(case,stage,steps);summarize()
