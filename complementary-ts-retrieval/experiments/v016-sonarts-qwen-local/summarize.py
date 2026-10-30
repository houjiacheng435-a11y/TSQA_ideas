"""Summarize measurements and SQL evidence access, without inferring failure cause."""
import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import statistics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    records = json.loads((a.out/'pilot10/records.json').read_text())
    tasks = {t['id']:t for t in json.loads((a.out/'tasks-selected.json').read_text())}
    assert len(records) == 10
    audits = []
    for r in records:
        tid = r['task_id']
        d = Path(r.get('reused_smoke_trace', a.out/'pilot10'/tid))
        queries, raw_times, raw_channels = [], set(), set()
        for p in sorted(d.glob('sql-*.jsonl.gz')):
            for line in gzip.open(p,'rt'):
                x = json.loads(line)
                if x['event'] == 'execute':
                    queries.append({'attempt':p.name, 'sql':x['sql'],'parameters':x['parameters']})
                if (x['event'] == 'fetchall' and 'raw_data' in x.get('sql','').lower()
                        and 'timestamp' in x.get('columns',[]) and len(x['columns']) > 1):
                    i = x['columns'].index('timestamp')
                    raw_times.update(str(row[i]) for row in x['rows'])
                    raw_channels.update(c for c in x['columns'] if c != 'timestamp')
        gt = tasks[tid].get('ground_truth',tasks[tid].get('answer'))
        audit = {'task_id':tid,'queries':queries,'n_queries':len(queries),
                 'unique_raw_timestamps_fetched':len(raw_times),'raw_channels_fetched':sorted(raw_channels),
                 'note':'Access is not proof of correct use. Code and intermediate values must be audited separately.'}
        if r['eval_metric'] == 'set_f1':
            days = {s[:10] for s in raw_times}
            audit['reference_dates_in_raw_fetch'] = [s for s in gt if s in days]
            audit['reference_dates_missing_from_raw_fetch'] = [s for s in gt if s not in days]
            audit['raw_days_fetched'] = len(days)
        elif r['eval_metric'] == 'iou':
            with sqlite3.connect(f'file:{a.out}/databases/{tid}.sqlite?mode=ro',uri=True) as conn:
                target = {s[0] for s in conn.execute('SELECT timestamp FROM raw_data WHERE timestamp >= ? AND timestamp <= ?',gt)}
            audit['reference_interval_raw_point_coverage'] = len(target & raw_times)/len(target) if target else None
        audits.append(audit)
    metrics = {}
    for key in ['wall_seconds','llm_seconds','input_tokens','output_tokens','llm_calls','code_failures','code_regenerations']:
        vals = [r[key] for r in records]
        metrics[key] = {'total':sum(vals),'mean':statistics.mean(vals),'min':min(vals),'max':max(vals)}
    by_task = collections.defaultdict(list)
    for r in records: by_task[r['subtask']].append(r['score'])
    mean_s = metrics['wall_seconds']['mean']
    summary = {'n':10,'all_execution_ok':all(r['final_status']=='ok' for r in records),
        'mean_official_score_descriptive_only':statistics.mean(r['score'] for r in records),
        'by_subtask':{k:{'n':len(v),'mean':statistics.mean(v)} for k,v in by_task.items()},
        'efficiency':metrics,'peak_resident_gpu_mib':max(r['peak_gpu_memory_mib'] for r in records),
        'sequential_linear_extrapolation':{str(n):{'hours':mean_s*n/3600,
            'cost_rmb_if_1_per_hour':mean_s*n/3600,'cost_rmb_if_2_per_hour':2*mean_s*n/3600,
            'cost_note':'Illustrative rates, not the actual AutoDL invoice. Excludes setup/offline indexing/other task mixes.'} for n in [100,1153]},
        'records_sha256':hashlib.sha256((a.out/'pilot10/records.json').read_bytes()).hexdigest()}
    for name,obj in [('summary.json',summary),('evidence-access-audit.json',audits)]:
        with (a.out/name).open('x') as f: json.dump(obj,f,ensure_ascii=False,indent=2)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == '__main__': main()
