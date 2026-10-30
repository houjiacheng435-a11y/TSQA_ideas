"""Package small reproducibility artifacts; no weights, old data or credentials."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
from core import save

HERE=Path(__file__).parent;OUT=HERE.parents[1]/'results/v018-conditional-evidence-value';ART=HERE/'artifacts'


def archive(target,files):
    with target.open('xb') as raw:
        with gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as gz:
            with tarfile.open(fileobj=gz,mode='w') as tar:
                for name,p in sorted(files.items()):
                    data=p.read_bytes();info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o644;info.mtime=0
                    tar.addfile(info,io.BytesIO(data))


def main():
    assert json.loads((OUT/'complete.json').read_text())['complete']
    ART.mkdir(exist_ok=True)
    cpu_names=['build-initial.log','build-audit.log','protocol.json','environment.json','families-private.json','gpu-episodes-private.json','reader-episodes-private.json',
        'audit.json','audit.complete.json','cpu.complete.json','cpu-test-summary.json','family-metrics.json','conditional-action-flips.json',
        'cpu-counterfactual-summary.json','development-selection.json','supplementary-ablations.json','supplementary.complete.json','cpu-trajectories.jsonl.gz']
    archive(ART/'cpu-and-audit.tar.gz',{n:OUT/n for n in cpu_names})
    files={'representative-cases.json':OUT/'representative-cases.json'}
    for directory in ['qwen-agents-schema','qwen-agents-documented','qwen-agents-neutral','qwen-readers','qwen-lag-control','chatts-readers']:
        for name in ['config.json','complete.json','records.json','script_snapshot.py']:
            p=OUT/directory/name
            if p.exists():files[directory+'/'+name]=p
        for p in (OUT/directory).glob('*/calls.jsonl'):files[str(p.relative_to(OUT))]=p
    archive(ART/'gpu-traces.tar.gz',files)
    summary={'protocol':json.loads((OUT/'protocol.json').read_text()),'cpu_test':json.loads((OUT/'cpu-test-summary.json').read_text()),
        'gpu':json.loads((OUT/'gpu-scores.json').read_text()),'complete':json.loads((OUT/'complete.json').read_text())}
    save(ART/'results.json',summary)
    # Excluded prototype is preserved server-side; include a transparent inventory.
    proto=OUT/'qwen-agents';calls=list(proto.glob('*/calls.jsonl'))
    completed=0;interrupted=0
    for p in calls:
        for line in p.read_text().splitlines():
            c=json.loads(line);completed+='response' in c;interrupted+='error' in c
    save(ART/'excluded-prototype.json',{'excluded':True,'reason':'Interface literal FETCH|STOP was copied; schema/valid actions required. Not a scored retrieval result.',
        'server_directory':str(proto),'completed_record_files':len(list(proto.glob('*/record.json'))),'api_responses':completed,'logged_errors':interrupted,
        'note':'An interrupted request may lack a response/error append. No data deleted or relabelled.'})
    sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.iterdir() if p.is_file() and p.name!='finish_gpu.sh'}
    artifacts={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in ART.iterdir() if p.is_file()}
    save(ART/'manifest.json',{'artifacts':artifacts,'source_sha256':sources,'note':'finish_gpu.sh is a server-only live PID orchestrator, deliberately not published. Historical reference/documented sources are in gpu-traces archive.'})
    print(json.dumps({p.name:p.stat().st_size for p in ART.iterdir() if p.is_file()},indent=2))


if __name__=='__main__':main()
