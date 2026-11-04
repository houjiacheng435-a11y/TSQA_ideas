"""只读审计全部 QA 配方、位置语义与底层原始记录重叠，不训练模型。"""
import bisect
import hashlib
import itertools
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from acquire_metadata import CACHE, HERE, SOURCE


def read_rows():
    rows = []
    for path in sorted((CACHE / "tasks").glob("*/*/*/data.parquet")):
        relative = str(path.relative_to(CACHE))
        for i, row in enumerate(pq.read_table(path).to_pylist()):
            row["row_id"] = relative + "#" + str(i)
            row["needles"] = json.loads(row["needles_json"])
            row["bouts"] = json.loads(row["other_bouts_json"])
            row["difficulty"] = json.loads(row["difficulty_config_json"])
            rows.append(row)
    return rows


def merge(intervals):
    result = []
    for a,b in sorted(intervals):
        if result and a <= result[-1][1]:
            result[-1][1] = max(b,result[-1][1])
        else:
            result.append([a,b])
    return result


def overlapping(a,b,intervals):
    ends = [x[1] for x in intervals]
    i = bisect.bisect_right(ends,a)
    return i < len(intervals) and intervals[i][0] < b


def recipe(row):
    # 相同背景加相同插入操作才是同输入；事件名称、答案和问句不参与指纹。
    fields = ("source_house_id", "source_meter_id", "source_start_ns", "source_end_ns",
              "insert_position_samples", "insert_duration_samples", "anomaly_class", "anomaly_params")
    needles = sorted((json.dumps({k:n.get(k) for k in fields},sort_keys=True) for n in row["needles"]))
    return json.dumps([row["background_house_id"],row["background_start_ns"],row["background_end_ns"],row["dt_s"],needles])


def main():
    rows = read_rows()
    assert len(list((CACHE/"tasks").glob("*/*/*/data.parquet"))) == 150
    valid = [r for r in rows if r["is_valid"]]
    result = {"total_rows":len(rows),"valid_rows":len(valid),"shards":[],"splits":{},"tasks":{},"pairing":{},"overlap":{},"limitations":["配方相同可证明输入相同，配方不同不能完全排除波形近重复", "Event Span 不是充分 Evidence Span", "本轮不生成新的配对 Query"]}
    for split in ("train","validation","test"):
        subset=[r for r in rows if r["split"]==split]
        result["splits"][split]={"rows":len(subset),"valid":sum(r["is_valid"] for r in subset),"invalid":sum(not r["is_valid"] for r in subset)}
    for task in sorted({r["task_type"] for r in rows}):
        subset=[r for r in valid if r["task_type"]==task]
        result["tasks"][task]={"valid":len(subset),"answer_types":dict(Counter(r["answer_type"] for r in subset)),"answers":dict(Counter(r["answer"] for r in subset)) if len({r["answer"] for r in subset})<30 else None,
                              "n_needles":dict(Counter(r["n_needles"] for r in subset)),"splits":dict(Counter(r["split"] for r in subset)),"examples":[{k:subset[0][k] for k in ("row_id","question","answer","answer_type","difficulty","needles","bouts")} ]}
    for ctx,task,split in itertools.product(sorted({r["context_length_s"] for r in rows}),result["tasks"],result["splits"]):
        subset=[r for r in rows if (r["context_length_s"],r["task_type"],r["split"])==(ctx,task,split)]
        result["shards"].append(dict(context_s=ctx,task=task,split=split,rows=len(subset),valid=sum(r["is_valid"] for r in subset),raw_samples=int(round(ctx/6))))
    groups=defaultdict(list)
    for row in valid:
        groups[recipe(row)].append(row)
    paired=[g for g in groups.values() if len({r["question"] for r in g})>1]
    result["pairing"]={"unique_recipes":len(groups),"duplicate_recipe_groups":sum(len(g)>1 for g in groups.values()),"multi_query_groups":len(paired),"examples":[[r["row_id"] for r in g] for g in paired[:10]]}
    backgrounds=defaultdict(list)
    for row in valid:
        backgrounds[row["background_house_id"],row["background_start_ns"],row["background_end_ns"]].append(row)
    result["pairing"]["exact_background_groups_multiple_rows"]=sum(len(g)>1 for g in backgrounds.values())
    result["question_templates"]={task:len({r["question"] for r in valid if r["task_type"]==task}) for task in result["tasks"]}
    # 逐周清单是官方声明；另独立核验背景实际起点所属周。
    manifest=json.loads((SOURCE/"split_manifest.json").read_text())
    week_split={(int(h),w):s for s in result["splits"] for h,w in manifest[s]}
    result["background_week_assignment"]={}
    for tz in ("UTC","Europe/London"):
        mismatch=Counter();total=Counter();examples=[]
        for row in valid:
            ts=pd.Timestamp(row["background_start_ns"],tz="UTC").tz_convert(tz)
            iso=ts.isocalendar();week=f"{iso.year}-W{iso.week:02d}"
            assigned=week_split.get((row["background_house_id"],week),"outside_manifest")
            total[row["split"]]+=1
            if assigned!=row["split"]:
                mismatch[row["split"]]+=1
                if len(examples)<6:examples.append(dict(row_id=row["row_id"],declared=row["split"],actual_week=week,week_split=assigned))
        result["background_week_assignment"][tz]={"total":dict(total),"mismatch":dict(mismatch),"examples":examples}
    by_split={s:defaultdict(list) for s in result["splits"]}
    needle_ids={s:set() for s in result["splits"]}
    for row in valid:
        by_split[row["split"]][row["background_house_id"]].append((row["background_start_ns"],row["background_end_ns"]))
        for n in row["needles"]:
            needle_ids[row["split"]].add((n["source_house_id"],n["source_meter_id"],n["source_start_ns"],n["source_end_ns"]))
    union={s:{h:merge(iv) for h,iv in houses.items()} for s,houses in by_split.items()}
    for a,b in itertools.combinations(result["splits"],2):
        left=[r for r in valid if r["split"]==a];right=[r for r in valid if r["split"]==b]
        hit_a=sum(overlapping(r["background_start_ns"],r["background_end_ns"],union[b].get(r["background_house_id"],[])) for r in left)
        hit_b=sum(overlapping(r["background_start_ns"],r["background_end_ns"],union[a].get(r["background_house_id"],[])) for r in right)
        questions_a={r["question"] for r in left}
        result["overlap"][a+"__"+b]={"left_background_rows_overlapping":hit_a,"right_background_rows_overlapping":hit_b,"exact_shared_source_bouts":len(needle_ids[a]&needle_ids[b]),
            "right_rows_exact_question_seen_left":sum(r["question"] in questions_a for r in right)}
    result["source_bout_reuse"]={s:dict(inserted_events=sum(r["n_needles"] for r in valid if r["split"]==s),unique_source_spans=len(needle_ids[s])) for s in result["splits"]}
    result["questions_containing_hhmm_pattern"]=sum(bool(re.search(r"\b\d{1,2}:\d{2}",r["question"])) for r in valid)
    # 使用完整 bout index 核对目标 OFF 假设，而非只看本 split 隐藏的 other_bouts。
    bouts=pq.read_table(CACHE/"bout_index.parquet").to_pylist()
    bout_lookup=defaultdict(list)
    for bout in bouts:bout_lookup[bout["house_id"],bout["appliance"]].append((bout["start_ns"],bout["end_ns"]))
    bout_union={key:merge(iv) for key,iv in bout_lookup.items()}
    contamination=Counter();totals=Counter();examples=[];negative=Counter()
    for row in valid:
        if row["task_type"]=="state_query":continue
        target=row["difficulty"].get("target")
        if not target:continue
        totals[row["task_type"]]+=1
        iv=bout_union.get((row["background_house_id"],target),[])
        if overlapping(row["background_start_ns"],row["background_end_ns"],iv):
            contamination[row["task_type"]]+=1
            if row["task_type"]=="existence" and row["answer"].lower()=="no":negative[row["split"]]+=1
            if len(examples)<12:examples.append(dict(row_id=row["row_id"],question=row["question"],answer=row["answer"],target=target))
    result["target_off_check"]={"checked":dict(totals),"background_overlaps_official_target_bout":dict(contamination),"existence_no_contradictions_by_split":dict(negative),"examples":examples,"meaning":"完整事件索引指出背景仍含目标活动；须原始波形复核，不直接等价为每题答案错误"}
    result["bout_index"]={"rows":len(bouts),"splits":dict(Counter(b["split"] for b in bouts)),"appliances":dict(Counter(b["appliance"] for b in bouts))}
    # 固定少量训练样本，仅选择有效性，不根据波形或方法表现挑选。
    selected=[]
    for ctx in (900,7200,86400):
        for task in ("existence","localization","ordering","multi_hop"):
            sample=next(r for r in valid if r["split"]=="train" and r["context_length_s"]==ctx and r["task_type"]==task)
            selected.append({k:v for k,v in sample.items() if k not in ("needles","bouts","difficulty")})
    (HERE/"selected_train_rows.json").write_text(json.dumps(selected,ensure_ascii=False,indent=2))
    (HERE/"audit_results.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({"splits":result["splits"],"pairing":result["pairing"],"overlap":result["overlap"],"weeks":result["background_week_assignment"]["UTC"]["mismatch"]},ensure_ascii=False))


if __name__=="__main__":main()
