"""Freeze a score-blind ten-task selection and build official features locally."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

FIXED_IDS = [
    'L2_T3_Subsequence_Matching_00332', 'L2_T3_Subsequence_Matching_00339',
    'L3_T3_Causal_Anomaly_00386', 'L3_T3_Causal_Anomaly_00387', 'L3_T3_Causal_Anomaly_00388',
    'L3_T1_Composite_Trend_00014', 'L3_T1_Composite_Trend_00025', 'L3_T1_Composite_Trend_00034',
    'L4_T1_Insight_Synthesis_00001', 'L4_T1_Insight_Synthesis_00002',
]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(p, obj):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write('\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--official', type=Path, required=True)
    ap.add_argument('--project', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(a.official))
    from sonar_ts import _paths
    _paths.DATABASES_DIR = a.out / 'databases'
    from sonar_ts.storage import TaskDatabase
    from sonar_ts.offline import compute_all_features
    import yaml
    tasks = json.loads((a.official / 'nlqtsbench/tasks.json').read_text())
    selected, sources = [], {}
    by_id = {t['id']: t for t in tasks}
    for tid in FIXED_IDS:
        t = by_id[tid]
        src = sorted((a.project / 'data').rglob(tid + '.csv'))[0]
        selected.append(t)
        sources[tid] = {'path': str(src), 'sha256': sha(src), 'bytes': src.stat().st_size}
    assert len(selected) == 10
    save(a.out / 'selection.json', {
        'rule': 'Before model inference: lexicographically first existing local CSV tasks per predefined family; 2 subsequence, 3 causal, 3 composite, 2 insight. No scores used.',
        'smoke_id': selected[0]['id'], 'ids': [t['id'] for t in selected],
        'sources': sources, 'official_commit': subprocess.check_output(['git','-C',str(a.official),'rev-parse','HEAD'], text=True).strip(),
        'tasks_sha256': sha(a.official / 'nlqtsbench/tasks.json')})
    save(a.out / 'tasks-selected.json', selected)
    cfg = yaml.safe_load((a.official / 'configs/offline.yaml').read_text())
    save(a.out / 'offline-config.json', cfg)
    built = []
    for t in selected:
        start = time.monotonic()
        dest = _paths.db_path_for(t['id'])
        assert not dest.exists()
        db = TaskDatabase.from_csv(t['id'], sources[t['id']]['path'], overwrite=False)
        feats = compute_all_features(db.fetch_raw_long(), cfg['views'], cfg['sax']['alphabet'])
        for name, df in feats.items():
            if not df.empty:
                db.write_feature_table(name, df)
        counts = {name: db.table_row_count(name) for name in ['raw_data', *feats]}
        db.close()
        record = {'id': t['id'], 'counts': counts, 'seconds': time.monotonic()-start, 'database_sha256': sha(dest)}
        built.append(record)
        print(json.dumps(record), flush=True)
    save(a.out / 'preparation.complete.json', {'complete': True, 'records': built})


if __name__ == '__main__':
    main()
