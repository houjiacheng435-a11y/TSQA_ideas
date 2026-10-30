"""Record non-secret environment/model identity; no inference or downloads."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', type=Path, required=True)
    ap.add_argument('--official', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    from safetensors import safe_open
    from transformers import AutoTokenizer
    idx = json.loads((a.model/'model.safetensors.index.json').read_text())
    files = sorted(set(idx['weight_map'].values()))
    tensors, dtypes, shards = set(), set(), []
    for name in files:
        p = a.model/name
        assert p.stat().st_size > 0
        with safe_open(p, framework='pt', device='cpu') as f:
            tensors.update(f.keys())
            dtypes.update(f.get_slice(k).get_dtype() for k in f.keys())
        shards.append({'name':name, 'bytes':p.stat().st_size})
    assert set(idx['weight_map']) <= tensors
    tok = AutoTokenizer.from_pretrained(a.model, local_files_only=True)
    prompt = tok.apply_chat_template([{'role':'user','content':'Return a Python program.'}],
                                    tokenize=False,add_generation_prompt=True,enable_thinking=False)
    assert prompt.endswith('<think>\n\n</think>\n\n')
    def command(args):
        return subprocess.check_output(args, text=True).strip()
    names = {p.metadata['Name'] for p in importlib.metadata.distributions() if p.metadata['Name']}
    # Resolve by sys.path priority: venv overrides must beat duplicate base installs.
    packages = {n:importlib.metadata.version(n) for n in sorted(names)}
    obj = {'python':sys.version,'executable':sys.executable,'packages':packages,
        'gpu':command(['nvidia-smi']), 'disk':command(['df','-h','/','/root/autodl-tmp']),
        'official_commit':command(['git','-C',str(a.official),'rev-parse','HEAD']),
        'official_diff':command(['git','-C',str(a.official),'diff','--stat']),
        'model_path':str(a.model), 'model_config':json.loads((a.model/'config.json').read_text()),
        'existing_download_manifest':json.loads((a.model/'download-manifest-v004.json').read_text()),
        'shards':shards,'tensor_count':len(tensors),'stored_dtypes':sorted(dtypes),
        'index_sha256':hashlib.sha256((a.model/'model.safetensors.index.json').read_bytes()).hexdigest(),
        'tokenizer_config_sha256':hashlib.sha256((a.model/'tokenizer_config.json').read_bytes()).hexdigest(),
        'nonthinking_template_probe':prompt}
    with a.out.open('x') as f: json.dump(obj,f,ensure_ascii=False,indent=2)
    print('Model shard/index and non-thinking template checks passed.')


if __name__ == '__main__': main()
