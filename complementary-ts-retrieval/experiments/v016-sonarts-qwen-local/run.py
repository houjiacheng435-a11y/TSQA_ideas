"""Run the official Sonar-TS pipeline with a loopback Qwen endpoint and tracing."""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.request
from urllib.parse import urlparse


class LocalClient:
    def __init__(self, base_url, task_dir):
        assert urlparse(base_url).hostname in {'localhost', '127.0.0.1', '::1'}
        self.base_url, self.task_dir, self.calls = base_url.rstrip('/'), task_dir, []

    def chat(self, messages):
        payload = {'model': 'Qwen3-8B', 'messages': messages, 'temperature': 0.0,
                   'max_tokens': 4096, 'chat_template_kwargs': {'enable_thinking': False}}
        req = urllib.request.Request(self.base_url + '/chat/completions',
              data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}, method='POST')
        start = time.monotonic()
        # Never send loopback requests through the server's external proxy.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        call = {'index': len(self.calls), 'request': payload}
        try:
            with opener.open(req, timeout=600) as resp:
                body = json.load(resp)
            call.update(response=body, seconds=time.monotonic()-start)
            return body['choices'][0]['message']['content']
        except Exception as exc:
            call.update(error=repr(exc), seconds=time.monotonic()-start)
            raise
        finally:
            self.calls.append(call)
            with (self.task_dir/'llm-calls.jsonl').open('a') as f:
                f.write(json.dumps(call, ensure_ascii=False)+'\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--official', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--phase', choices=['smoke','pilot10'], required=True)
    ap.add_argument('--base-url', default='http://127.0.0.1:8016/v1')
    a = ap.parse_args()
    sys.path.insert(0, str(a.official))
    from sonar_ts import _paths
    _paths.DATABASES_DIR = a.out/'databases'
    from sonar_ts import pipeline, executor, evaluator
    import yaml
    cfg = yaml.safe_load((a.official/'configs/online.yaml').read_text())
    executor_cfg = dict(cfg['executor'], shape_rules=cfg['shape_rules'])
    tasks = json.loads((a.out/'tasks-selected.json').read_text())
    if a.phase == 'smoke':
        tasks = tasks[:1]
    else:
        gate = json.loads((a.out/'smoke'/tasks[0]['id']/'record.json').read_text())
        assert gate['final_status'] == 'ok', 'Full-system smoke test must pass first.'
    dest = a.out/a.phase
    dest.mkdir(exist_ok=True)
    run_config = {'label':'Sonar-TS + Qwen3-8B','official':str(a.official),
        'base_url':a.base_url,'workers':1,'max_tokens':4096,'temperature':0.0,
        'thinking':False,'dtype':'bfloat16','context_limit':16384,
        'executor_config':executor_cfg,'phase':a.phase,'task_ids':[t['id'] for t in tasks],
        'client_http_timeout_seconds':600,'paid_api':False}
    if not (dest/'run-config.json').exists():
        with (dest/'run-config.json').open('x') as f:
            json.dump(run_config,f,ensure_ascii=False,indent=2)
    executor._RUNNER = Path(__file__).with_name('traced_runner.py')
    official_execute = executor.execute
    predictions, records = [], []
    for idx, task in enumerate(tasks):
        task_dir = dest/task['id']
        if (task_dir/'record.json').exists():
            r = json.loads((task_dir/'record.json').read_text())
            predictions.append({'id': idx, 'prediction': r['prediction']})
            records.append(r)
            continue
        # Reuse the exact smoke result as one of the ten; do not repeat GPU work.
        smoke = a.out/'smoke'/task['id']
        if a.phase == 'pilot10' and (smoke/'record.json').exists():
            r = json.loads((smoke/'record.json').read_text())
            r['reused_smoke_trace'] = str(smoke)
            task_dir.mkdir()
            (task_dir/'record.json').write_text(json.dumps(r, ensure_ascii=False, indent=2))
            predictions.append({'id': idx, 'prediction': r['prediction']})
            records.append(r)
            continue
        task_dir.mkdir(exist_ok=False)
        client = LocalClient(a.base_url, task_dir)
        attempt = [0]

        def observed_execute(code, task_id, eval_metric, **kwargs):
            n = attempt[0]
            attempt[0] += 1
            (task_dir/f'code-{n}.py').write_text(code)
            os.environ['V016_SQL_TRACE'] = str(task_dir/f'sql-{n}.jsonl.gz')
            os.environ['V016_OFFICIAL_RUNNER'] = str(a.official/'sonar_ts/_runner.py')
            start = time.monotonic()
            result = official_execute(code, task_id, eval_metric, **kwargs)
            info = asdict(result)
            info['seconds'] = time.monotonic()-start
            (task_dir/f'execution-{n}.json').write_text(json.dumps(info, ensure_ascii=False, indent=2))
            return result

        executor.execute = observed_execute
        stop = threading.Event()
        samples = []

        def monitor():
            while not stop.is_set():
                try:
                    v = subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True).strip()
                    mem, util = map(int,v.split(','))
                    samples.append({'elapsed': time.monotonic()-started,'memory_mib':mem,'utilization':util})
                except Exception:
                    pass
                stop.wait(.5)

        started = time.monotonic()
        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
        rec = pipeline.run_task(task, client, executor_config=executor_cfg)
        elapsed = time.monotonic()-started
        stop.set()
        thread.join()
        r = asdict(rec)
        score, breakdown = evaluator.score_one(task['eval_metric'], rec.prediction, task.get('ground_truth',task.get('answer')))
        r.update(question=task['question'], subtask=task['subtask'], eval_metric=task['eval_metric'],
                 score=score, score_breakdown=breakdown, wall_seconds=elapsed,
                 llm_seconds=sum(c['seconds'] for c in client.calls), llm_calls=len(client.calls),
                 input_tokens=sum(c.get('response',{}).get('usage',{}).get('prompt_tokens',0) for c in client.calls),
                 output_tokens=sum(c.get('response',{}).get('usage',{}).get('completion_tokens',0) for c in client.calls),
                 peak_gpu_memory_mib=max((s['memory_mib'] for s in samples),default=None),
                 code_failures=sum(x['status']!='ok' for x in rec.executor_log),
                 code_regenerations=max(0,len(rec.code_attempts)-1))
        (task_dir/'record.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
        (task_dir/'gpu-samples.json').write_text(json.dumps(samples))
        records.append(r)
        predictions.append({'id':idx,'prediction':rec.prediction})
        print(json.dumps({k:r[k] for k in ['task_id','final_status','score','wall_seconds','llm_calls','output_tokens']}, ensure_ascii=False),flush=True)
    (dest/'predict.json').write_text(json.dumps(predictions,ensure_ascii=False,indent=2))
    (dest/'records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
    (dest/'complete.json').write_text(json.dumps({'complete':True,'records':len(records),'all_execution_ok':all(r['final_status']=='ok' for r in records)},indent=2))


if __name__ == '__main__':
    main()
