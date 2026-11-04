"""按实际信号读取时间区间核验源隔离，生成只读筛选清单；不改官方数据。"""
import bisect
import itertools
import json
from collections import Counter,defaultdict
from functools import lru_cache

import pandas as pd
import pyarrow.parquet as pq

from acquire_metadata import CACHE,HERE,SOURCE
from audit_metadata import merge,overlapping,read_rows


@lru_cache(maxsize=None)
def week_of(timestamp):
    iso=pd.Timestamp(timestamp,tz="UTC").isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def main():
    rows=[r for r in read_rows() if r["is_valid"]]
    manifest=json.loads((SOURCE/"split_manifest.json").read_text())
    assignment={(int(h),w):s for s in ("train","validation","test") for h,w in manifest[s]}
    def assigned_span(house,a,b,split):
        # 官方单个背景最多一天，源事件也小于一周；跨周时两侧都必须在本划分。
        assert b-a < 7*86400*10**9
        return all(assignment.get((house,week_of(t)))==split for t in (a,b-1))
    by_split=defaultdict(list)
    for r in rows:by_split[r["split"]].append(r)
    witnesses=[]
    for a,b in itertools.combinations(("train","validation","test"),2):
        per_house=defaultdict(list)
        for r in by_split[b]:per_house[r["background_house_id"]].append(r)
        found=False
        for r in by_split[a]:
            for s in per_house[r["background_house_id"]]:
                start=max(r["background_start_ns"],s["background_start_ns"])
                end=min(r["background_end_ns"],s["background_end_ns"])
                if start<end:
                    witnesses.append(dict(left=r["row_id"],right=s["row_id"],house=r["background_house_id"],
                                          overlap_start_ns=start,overlap_end_ns=end,overlap_s=(end-start)/1e9))
                    found=True;break
            if found:break
    bouts=pq.read_table(CACHE/"bout_index.parquet").to_pylist()
    lookup=defaultdict(list)
    for b in bouts:lookup[b["house_id"],b["appliance"]].append((b["start_ns"],b["end_ns"]))
    lookup={k:merge(v) for k,v in lookup.items()}
    stages=defaultdict(Counter);clean_ids=[];clean_by_task=Counter();negative_witness=None
    for r in rows:
        split=r["split"];delta=int(r["dt_s"]*1e9)
        # 计入重建函数的前置 2 个采样间隔与源事件末端附加 1 个间隔。
        background_ok=assigned_span(r["background_house_id"],r["background_start_ns"]-2*delta,r["background_end_ns"],split)
        if background_ok:stages[split]["background_source_week_safe"]+=1
        needle_ok=all(assigned_span(n["source_house_id"],n["source_start_ns"]-2*delta,n["source_end_ns"]+delta,split) for n in r["needles"])
        if background_ok and needle_ok:
            stages[split]["all_read_windows_week_safe"]+=1
            # 候选清单只依赖时间与官方划分，不依赖任何划分的问答标签或事件冲突检查。
            clean_ids.append(r["row_id"]);clean_by_task[split,r["task_type"]]+=1
        targets=[r["difficulty"][k] for k in ("target","anchor","appliance_a","appliance_b") if k in r["difficulty"]]
        conflicts=[t for t in targets if overlapping(r["background_start_ns"],r["background_end_ns"],lookup.get((r["background_house_id"],t),[]))]
        if background_ok and needle_ok and (not conflicts or r["task_type"]=="state_query"):
            stages[split]["week_safe_and_no_index_off_conflict"]+=1
        if negative_witness is None and split=="train" and r["task_type"]=="existence" and r["answer"]=="No" and conflicts:
            target=r["difficulty"]["target"]
            b=next(b for b in bouts if b["house_id"]==r["background_house_id"] and b["appliance"]==target and b["start_ns"]<r["background_end_ns"] and b["end_ns"]>r["background_start_ns"])
            negative_witness=dict(row_id=r["row_id"],question=r["question"],answer=r["answer"],
                                  background_house_id=r["background_house_id"],background_start_ns=r["background_start_ns"],
                                  background_end_ns=r["background_end_ns"],official_bout=b,
                                  label_semantics_warning="官方事件索引冲突，还未用原始分表波形复核，不宣布所有此类题都错标")
    result=dict(timezone="UTC",official_week_counts={s:len(manifest[s]) for s in by_split},
        overlap_witnesses=witnesses,source_safe_stages={s:dict(v) for s,v in stages.items()},
        filtered_counts=[dict(split=s,task=t,n=n) for (s,t),n in sorted(clean_by_task.items())],
        negative_existence_index_witness=negative_witness,
        limitations=["只读候选筛选不是新官方划分", "同 house 的设备签名仍共享，不是跨住户泛化", "完整事件索引仍不是全部真实活动的无误标注", "未做全库波形近重复检测"])
    (HERE/"source_isolation.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
    (HERE/"source_safe_row_ids.json").write_text(json.dumps(clean_ids,indent=2))
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
