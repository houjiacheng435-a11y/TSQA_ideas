"""仅诊断选定子集的完全重复、近重复与官方标签敏感性，不改样本或答案。"""
import hashlib
import json
from collections import Counter
import numpy as np
import pyarrow.parquet as pq
from data import groups,signal_path
from paths import HERE,CACHE


def main(long=False):
    plan=groups();keys=('long_train','long_validation','long_test') if long else ('train','validation','test');collections={k:plan[k] for k in keys};arrays={};hashes={};missing=[]
    for group,rows in collections.items():
        for row in rows:
            path=signal_path(row)
            if not path.exists():missing.append(row['row_id']);continue
            x=np.load(path);key=row['row_id'];arrays[key]=x
            hashes[key]=hashlib.sha256(x.tobytes()).hexdigest()
    duplicates=[];near=[];background_overlap=[]
    for ga,gb in ((keys[0],keys[1]),(keys[0],keys[2]),(keys[1],keys[2])):
        for a in collections[ga]:
            for b in collections[gb]:
                ka,kb=a['row_id'],b['row_id']
                if a['background_house_id']==b['background_house_id'] and max(a['background_start_ns'],b['background_start_ns'])<min(a['background_end_ns'],b['background_end_ns']):background_overlap.append([ka,kb])
                if ka not in arrays or kb not in arrays:continue
                if hashes[ka]==hashes[kb]:duplicates.append([ka,kb])
                x,y=arrays[ka],arrays[kb]
                if len(x)!=len(y):continue
                rmse=float(np.sqrt(np.mean((x.astype(float)-y)**2)))
                nrmse=rmse/max(float(np.std(x)),float(np.std(y)),1.)
                if np.std(x)>0 and np.std(y)>0:
                    corr=float(np.corrcoef(x,y)[0,1])
                    if corr>.999 and nrmse<.01:near.append(dict(rows=[ka,kb],correlation=corr,normalized_rmse=nrmse))
    # 背景中真实设备源活动可能与官方No冲突；只能标记风险，不能据此改标签。
    bouts=pq.read_table(CACHE/'bout_index.parquet').to_pylist();flags=[]
    for group,rows in collections.items():
        for row in rows:
            if row['task_type']!='existence' or row['answer'].lower()!='no':continue
            target=json.loads(row['difficulty_config_json'])['target'];matches=[]
            for bout in bouts:
                if bout.get('house_id')==row['background_house_id'] and bout.get('appliance')==target:
                    # 字段名以官方parquet实际schema为准。
                    a=bout.get('start_ns',bout.get('start_timestamp_ns'));b=bout.get('end_ns',bout.get('end_timestamp_ns'))
                    if a is not None and b is not None and max(a,row['background_start_ns'])<min(b,row['background_end_ns']):matches.append(bout)
            if matches:flags.append(dict(group=group,row_id=row['row_id'],target=target,n_bouts=len(matches)))
    counts={k:dict(Counter((r['task_type']+(':'+r['answer'] if r['task_type']=='existence' else '')) for r in rows)) for k,rows in collections.items()}
    question_overlap={ga+'_'+gb:sum(r['question'] in {x['question'] for x in collections[ga]} for r in collections[gb]) for ga,gb in [(keys[0],keys[1]),(keys[0],keys[2])]}
    result=dict(counts=counts,question_exact_overlap_count=question_overlap,missing=missing,exact_cross_split_duplicates=duplicates,near_duplicates=near,near_criterion='same native length, correlation>.999 AND RMSE/max(std_x,std_y,1W)<.01',background_overlap_pairs=background_overlap,existence_no_background_index_conflicts=flags)
    (HERE/('results/input_audit_long.json' if long else 'results/input_audit.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2));print({k:len(v) if isinstance(v,list) else v for k,v in result.items()})


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--long',action='store_true')
    main(parser.parse_args().long)
