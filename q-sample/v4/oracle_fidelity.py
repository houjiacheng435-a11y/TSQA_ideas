"""比较特权采样启发式的波形重建，不把事件命中率冒充证据充分性或 QA 准确率。"""
import heapq
import json
from collections import defaultdict

import numpy as np

from acquire_metadata import CACHE,HERE

BUDGETS = (16,32,64,128,512)
CONTEXT = 10  # 固定前后各 60 秒；这是审计代理，不是官方证据标注。


def event_intervals(row):
    return [(int(n["insert_position_samples"]),int(n["insert_position_samples"]+n["insert_duration_samples"]))
            for n in json.loads(row["needles_json"])]


def relevant_intervals(row):
    needles = json.loads(row["needles_json"])
    cfg = json.loads(row["difficulty_config_json"])
    task = row["task_type"]
    selected = list(range(len(needles)))
    if task in ("existence","localization"):
        selected = sorted([i for i,n in enumerate(needles) if n["appliance"]==cfg["target"]],
                          key=lambda i:needles[i]["insert_position_samples"])
        if task=="localization":selected=selected[:cfg["k"]]
    elif task=="multi_hop":
        anchors=sorted([i for i,n in enumerate(needles) if n["appliance"]==cfg["anchor"]],key=lambda i:needles[i]["insert_position_samples"])
        prefix=anchors[:cfg["j"]]
        anchor_position=needles[prefix[-1]]["insert_position_samples"]
        targets=sorted([i for i,n in enumerate(needles) if n["appliance"]==cfg["target"]],key=lambda i:needles[i]["insert_position_samples"])
        after=[i for i in targets if needles[i]["insert_position_samples"]>anchor_position]
        chosen=after[cfg["k"]-1]
        selected=prefix+[i for i in targets if needles[i]["insert_position_samples"]<=needles[chosen]["insert_position_samples"]]
    intervals=event_intervals(row)
    return [intervals[i] for i in selected]


def mask(length, intervals, padding=0):
    output=np.zeros(length,dtype=bool)
    for a,b in intervals:output[max(0,a-padding):min(length,b+padding)]=True
    return output


def greedy_order(signal, weights):
    """按加权线性重建残差逐段细分；不规定每个事件必须分配几个点。"""
    queue=[]
    def add(a,b):
        if b-a<2:return
        indices=np.arange(a+1,b)
        estimate=signal[a]+(signal[b]-signal[a])*(indices-a)/(b-a)
        error=weights[indices]*(signal[indices]-estimate)**2
        k=int(np.argmax(error))
        heapq.heappush(queue,(-float(error[k]),a,b,int(indices[k])))
    add(0,len(signal)-1)
    order=[0,len(signal)-1]
    while queue and len(order)<min(512,len(signal)):
        _,a,b,index=heapq.heappop(queue)
        order.append(index)
        add(a,index);add(index,b)
    return order


def main():
    import pyarrow.parquet as pq
    full_bouts=pq.read_table(CACHE/"bout_index.parquet").to_pylist()
    by_house=defaultdict(list)
    for b in full_bouts:by_house[b["house_id"]].append(b)
    rows=json.loads((HERE/"selected_train_rows.json").read_text())
    source_safe=set(json.loads((HERE/"source_safe_row_ids.json").read_text()))
    acquisition=json.loads((HERE/"signal_acquisition.json").read_text())
    by_id={r["row_id"]:r for r in acquisition["results"] if r["status"]=="ok"}
    results=[]
    examples=[]
    for row in rows:
        if row["row_id"] not in by_id:continue
        signal=np.load(by_id[row["row_id"]]["path"]).astype(np.float64)
        length=len(signal)
        target_intervals=relevant_intervals(row)
        target=mask(length,target_intervals)
        context=mask(length,target_intervals,CONTEXT)
        absence=not target.any()
        if absence:target[:]=True;context[:]=True
        # 盲方法可以看到全部官方事件；不读取问句、答案或当前目标类别。
        all_events=event_intervals(row)+[(b["start_sample"],b["end_sample"]) for b in json.loads(row["other_bouts_json"])]
        delta=int(row["dt_s"]*1e9)
        for b in by_house[row["background_house_id"]]:
            if b["start_ns"]<row["background_end_ns"] and b["end_ns"]>row["background_start_ns"]:
                a=max(0,(b["start_ns"]-row["background_start_ns"])//delta)
                end=min(length,(b["end_ns"]-row["background_start_ns"])//delta+1)
                all_events.append((a,end))
        all_events=sorted(set(all_events))
        event_weight=np.full(length,.02)
        for a,b in all_events:
            a=max(0,a-CONTEXT);b=min(length,b+CONTEXT)
            if b>a:event_weight[a:b]+=1/(b-a)
        event_weight/=max(float(event_weight.max()),1e-10)
        weights={"aware_proxy":np.where(context,1.0,.02),"blind_global":np.ones(length),"blind_all_events":event_weight}
        orders={name:greedy_order(signal,weight) for name,weight in weights.items()}
        scale=max(float(np.std(signal)),1.0)
        for budget in BUDGETS:
            grids={name:np.sort(order[:min(budget,length)]) for name,order in orders.items()}
            grids["uniform"]=np.unique(np.rint(np.linspace(0,length-1,min(budget,length))).astype(int))
            for method,grid in grids.items():
                # 所有方法只把相同精度的真实采样值和坐标交给相同的线性重建器。
                coordinates=grid.astype(np.float32)
                values=signal[grid].astype(np.float32)
                restored=np.interp(np.arange(length),coordinates,values)
                residual=(restored-signal)**2
                hits=[bool(np.any((grid>=a)&(grid<b))) for a,b in target_intervals]
                results.append(dict(row_id=row["row_id"],task=row["task_type"],length=length,budget=budget,
                                    source_week_safe=row["row_id"] in source_safe,
                                    method=method,unique_samples=len(grid),absence_proxy=absence,
                                    event_hit_rate=float(np.mean(hits)) if hits else None,
                                    target_occupancy=float(target[grid].mean()) if not absence else None,
                                    target_nrmse=float(np.sqrt(residual[target].mean())/scale),
                                    context_nrmse=float(np.sqrt(residual[context].mean())/scale),
                                    global_nrmse=float(np.sqrt(residual.mean())/scale)))
                if row["context_length_s"]==86400 and row["task_type"]=="localization" and budget==32:
                    examples.append((row,signal,grid,method,target_intervals))
    grouped=defaultdict(list)
    for r in results:grouped[r["method"],r["budget"]].append(r)
    summary=[]
    for (method,budget),records in sorted(grouped.items()):
        summary.append(dict(method=method,budget=budget,n=len(records),
                            **{key:float(np.mean([r[key] for r in records if r[key] is not None]))
                               for key in ("event_hit_rate","target_nrmse","context_nrmse","global_nrmse")}))
    output=dict(description="只验证事件及背景的波形重建代理；没有配对 Query、没有答案头、没有 QA 准确率，不能称为严格最优 Oracle 上界。",
                budgets=BUDGETS,context_samples=CONTEXT,results=results,summary=summary,
                source_week_safe_selected=sum(r["row_id"] in source_safe for r in rows),
                limitations=["特权启发式均非最优采样求解器", "blind_all_events 使用完整 bout_index 加全部插入事件，索引遗漏活动仍可能存在", "目标区间及上下文只是代理，不是充分证据标注", "仅训练集固定 12 题，不用于总体结论或选择测试超参数"])
    (HERE/"oracle_fidelity_results.json").write_text(json.dumps(output,ensure_ascii=False,indent=2))
    if examples:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig,axes=plt.subplots(len(examples),1,figsize=(12,8),sharex=True)
        for ax,(row,signal,grid,method,intervals) in zip(axes,examples):
            ax.plot(np.arange(len(signal))*6/3600,signal,lw=.45,color=".45")
            ax.scatter(grid*6/3600,signal[grid],s=13,color="tab:red")
            for a,b in intervals:ax.axvspan(a*6/3600,b*6/3600,alpha=.18,color="tab:green")
            ax.set_ylabel("W");ax.set_title(method+" | N=32",fontsize=10)
        axes[-1].set_xlabel("Hours from window start; green = proxy regions")
        fig.tight_layout();fig.savefig(HERE/"oracle_sampling.png",dpi=150);plt.close(fig)
    print(json.dumps(summary,indent=2))


if __name__=="__main__":main()
