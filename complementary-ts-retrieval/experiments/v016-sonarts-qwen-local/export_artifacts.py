"""Publish small reproducibility artifacts, excluding raw series and SQL row dumps."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--out', type=Path, required=True)
ap.add_argument('--dest', type=Path, help='New directory; existing published artifacts are never overwritten.')
a = ap.parse_args()
dest = a.dest or Path(__file__).parent/'artifacts'
dest.mkdir(exist_ok=False)
files = ['selection.json','tasks-selected.json','offline-config.json','environment-verified.json',
         'preparation.complete.json','instrumentation-selfcheck.complete.json',
         'summary.json','official-summary.json','official-per-task.json',
         'evidence-access-audit.json','failure-audit.json','audit.complete.json','pilot10/run-config.json']
for rel in files:
    p = a.out/rel
    with (dest/Path(rel).name).open('xb') as f: f.write(p.read_bytes())
records = json.loads((a.out/'pilot10/records.json').read_text())
traces = []
for r in records:
    d = Path(r.get('reused_smoke_trace',a.out/'pilot10'/r['task_id']))
    traces.append({'record':r,
        'llm_calls':[json.loads(s) for s in (d/'llm-calls.jsonl').read_text().splitlines()],
        'executions':[json.loads(p.read_text()) for p in sorted(d.glob('execution-*.json'))]})
with gzip.open(dest/'full-system-traces.json.gz','wt',encoding='utf-8') as f:
    json.dump(traces,f,ensure_ascii=False)
manifest = []
for p in sorted(a.out.rglob('*')):
    if p.is_file():
        h = hashlib.sha256()
        with p.open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
        manifest.append({'path':str(p.relative_to(a.out)),'bytes':p.stat().st_size,'sha256':h.hexdigest()})
with (dest/'server-artifact-manifest-final.json').open('x') as f:json.dump(manifest,f,ensure_ascii=False,indent=2)
print('Published small configs, scores, code/LLM traces and server file hashes; excluded raw series/SQL rows/databases/weights.')
