"""CPU-only check: logging preserves query output and records SQL result rows."""
import argparse
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ap = argparse.ArgumentParser()
ap.add_argument('--official', type=Path, required=True)
ap.add_argument('--out', type=Path, required=True)
a = ap.parse_args()
task = json.loads((a.out/'selection.json').read_text())['smoke_id']
db = a.out/'databases'/f'{task}.sqlite'
trace = a.out/'instrumentation-selfcheck.jsonl.gz'
assert not trace.exists()
with tempfile.TemporaryDirectory(prefix='v016-selfcheck-') as tmp:
    p = Path(tmp)/'query.py'
    p.write_text("rows = conn.execute('SELECT window_start FROM daily_feature LIMIT 2').fetchall()\n_result = [r[0] for r in rows]\nimport json\nprint(json.dumps({'_result':_result}))\n")
    orig = a.official/'sonar_ts/_runner.py'
    ordinary = subprocess.check_output([sys.executable,str(orig),str(db),str(p)],text=True)
    env = dict(os.environ,V016_SQL_TRACE=str(trace),V016_OFFICIAL_RUNNER=str(orig))
    logged = subprocess.check_output([sys.executable,str(Path(__file__).with_name('traced_runner.py')),str(db),str(p)],env=env,text=True)
    assert ordinary == logged
events = [json.loads(s) for s in gzip.open(trace,'rt')]
assert any(r['event']=='fetchall' and r['n']==2 for r in events)
assert any(r['event']=='final_variables' for r in events)
with (a.out/'instrumentation-selfcheck.complete.json').open('x') as f:
    json.dump({'complete':True,'same_stdout':True,'sql_rows_captured':True,'final_variables_captured':True},f,indent=2)
print('Trace wrapper preserves official SQL output; candidates and final variables captured.')
