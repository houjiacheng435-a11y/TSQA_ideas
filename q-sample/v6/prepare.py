"""固定官方Localization子集，复用v5波形与文本缓存，不加载官方Test。"""
import argparse
import hashlib
import json
from collections import Counter
import numpy as np
import pyarrow.parquet as pq
import torch
from legacy import HERE,CACHE,REVISION,v5_model,source_io


def metadata(split,context):
    relative=f'tasks/{context}s/localization/{split}/data.parquet'
    rows=[]
    for i,row in enumerate(pq.read_table(CACHE/relative).to_pylist()):
        if row['is_valid']:row['row_id']=relative+'#'+str(i);rows.append(row)
    return rows


def plan():
    previous=json.loads((HERE.parent/'v5/data_plan.json').read_text())['groups']
    overfit=[r.copy() for r in previous['train'] if r['task_type']=='localization']
    groups={'overfit':overfit,'train':[],'validation':[]}
    for context in (7200,32400):
        old=[r for r in overfit if r['context_length_s']==context]
        for split,count in [('train',512),('validation',64)]:
            rows=metadata(split,context)
            order=sorted(rows,key=lambda r:hashlib.sha256(('qsample-v6:'+r['row_id']).encode()).hexdigest())
            if split=='train':order=old+[r for r in order if r['row_id'] not in {o['row_id'] for o in old}]
            groups[split]+=order[:count]
    payload=dict(revision=REVISION,selection='固定row_id哈希顺序；Train纳入32道v5已缓存定位题；不使用Test',groups=groups)
    path=HERE/'data_plan.json'
    if path.exists():assert json.loads(path.read_text())==payload
    else:path.write_text(json.dumps(payload,ensure_ascii=False))
    print({key:len(rows) for key,rows in groups.items()},flush=True)
    return payload


@torch.no_grad()
def text(plan):
    path=CACHE/'v6_text_embeddings.pt'
    queries=sorted({r['question'] for rows in plan['groups'].values() for r in rows})
    if path.exists():
        payload=torch.load(path,weights_only=True)
        assert payload['questions']==queries
        return
    encoder=v5_model.FrozenText().cuda().eval();embeddings=[]
    for i in range(0,len(queries),64):embeddings.append(encoder(queries[i:i+64]).cpu())
    torch.save(dict(questions=queries,embeddings=torch.cat(embeddings)),path)
    print('冻结文本编码',len(queries),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--groups',nargs='+',default=['overfit','train','validation']);parser.add_argument('--workers',type=int,default=12);args=parser.parse_args()
    document=plan();text(document)
    rows={r['row_id']:r for group in args.groups for r in document['groups'][group]}
    outcomes=source_io.reconstruct(list(rows.values()),max_workers=args.workers)
    if any(r['status']!='ok' for r in outcomes):raise SystemExit('窗口下载未全成功；固定清单不变，重新运行补齐缓存')
