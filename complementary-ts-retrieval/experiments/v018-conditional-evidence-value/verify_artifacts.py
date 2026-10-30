"""Read-only, CPU-only verification of archived v018 observations and decisions."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
from core import Broker,make_family,make_episode,required,phase

HERE=Path(__file__).parent


def members(path):
    with tarfile.open(path,'r:gz') as arc:
        # Read members without filesystem extraction or executing archived code.
        return {m.name:arc.extractfile(m).read() for m in arc.getmembers() if m.isfile()}


def main():
    a=HERE/'artifacts';manifest=json.loads((a/'manifest.json').read_text())
    for name,m in manifest['artifacts'].items():
        data=(a/name).read_bytes();assert len(data)==m['bytes'];assert hashlib.sha256(data).hexdigest()==m['sha256'],name
    for name,sha in manifest['source_sha256'].items():
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==sha,name
    cpu=members(a/'cpu-and-audit.tar.gz');gpu=members(a/'gpu-traces.tar.gz')
    fs={f['id']:f for f in json.loads(cpu['families-private.json'])}
    for f in fs.values():assert make_family(f['seed'],f['split'],f['index'])==f
    assert len(fs)==96 and sum(f['split']=='test' for f in fs.values())==48
    assert json.loads(cpu['audit.complete.json'])['gpu_gate_passed']
    n=0
    for name,total in [('qwen-agents-schema',960),('qwen-agents-documented',960),('qwen-agents-neutral',288)]:
        rows=json.loads(gpu[name+'/records.json']);assert len(rows)==total
        for r in rows:
            e=r['episode'];assert fs[e['family']]['split']=='test'
            b=Broker(fs[e['family']],e,3)
            assert r['truth']==('YES' if e['ys'][e['source']]==0 else 'NO')
            for d in r['decisions']:
                assert b.public()==d['public_state']
                assert b.state()==d['numeric_state_before']
                if 'obtained' in d:assert b.fetch(d['parsed']['id'])==d['obtained']
            assert b.selected==r['selected'] and b.state()==r['final_numeric']
            if b.state()['sufficient']:assert b.state()['answer']==r['truth']
            n+=1
    # Explicit paired-world test: same source/candidate previews, opposite label;
    # same full candidate pool, different source context and relevant bundle.
    for f in fs.values():
        for depth in range(3):
            a0=Broker(f,make_episode(f,depth,(0,1),0));a1=Broker(f,make_episode(f,depth,(0,1),1))
            flip=Broker(f,make_episode(f,depth,(1,0),0))
            assert a0.records==a1.records and a0.known_group!=a1.known_group
            assert a0.public()==flip.public()
    counts={name:len(json.loads(gpu[name+'/records.json'])) for name in ['qwen-readers','qwen-lag-control','chatts-readers']}
    assert counts=={'qwen-readers':864,'qwen-lag-control':288,'chatts-readers':576}
    print(json.dumps({'verified':True,'dynamic_episodes_replayed':n,'families':len(fs),'reader_counts':counts,'gpu_used':False}))


if __name__=='__main__':main()
