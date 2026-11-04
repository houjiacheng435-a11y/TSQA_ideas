"""复用固定官方评分函数，检查答案解析、事件位置语义和不读波形的训练先验。"""
import ast
import hashlib
import json
from collections import Counter,defaultdict

from audit_metadata import read_rows
from acquire_metadata import HERE
from signal_diagnostic import OFFICIAL


def scorer():
    utils=OFFICIAL/"src/datasets/capture24_haystack/utils"
    namespace={}
    exec(compile((utils/"timestamp_utils.py").read_text(),str(utils/"timestamp_utils.py"),"exec"),namespace)
    tree=ast.parse((utils/"answer_evaluation.py").read_text())
    # 只跳过框架包导入；所需时间解析函数已经执行官方原文件，未改动评分逻辑。
    tree.body=[n for n in tree.body if not (isinstance(n,ast.ImportFrom) and (n.module or "").startswith("src."))]
    exec(compile(tree,str(utils/"answer_evaluation.py"),"exec"),namespace)
    return namespace


def main():
    rows=[r for r in read_rows() if r["is_valid"]]
    official=scorer()
    evaluate=official["evaluate_answer"]
    counts=Counter();failures=[];position_errors=[];coordinate_outputs=[]
    for row in rows:
        okay=evaluate(row["answer"],row["answer"],row["answer_type"],iou_threshold=.25,timestamp_tolerance_s=6)["correct"]
        counts[row["split"],"ok" if okay else "failed"]+=1
        if not okay:failures.append(row["row_id"])
        if row["task_type"]=="localization":
            targets=sorted([n for n in row["needles"] if n["appliance"]==row["difficulty"]["target"]],key=lambda n:n["insert_position_samples"])
            target=targets[row["difficulty"]["k"]-1]
            # 官方答案是相对窗口起点；needle.timestamp_* 则是背景对应的 UTC 钟表时间。
            def hms(samples):
                value=int(samples*row["dt_s"])
                return f"{value//3600:02d}:{value//60%60:02d}:{value%60:02d}"
            a=target["insert_position_samples"];b=a+target["insert_duration_samples"]
            expected=hms(a)+" - "+hms(b)
            if expected!=row["answer"]:position_errors.append(dict(row_id=row["row_id"],answer=row["answer"],expected=expected))
            if row["split"]=="train":
                # 人工答案端点选点器：证明坐标通道可携带答案；不是实际模型或有效 QA 结果。
                coordinate_outputs.append(evaluate(row["answer"],expected,row["answer_type"])["correct"])
    train_counts=defaultdict(Counter);question_counts=defaultdict(Counter)
    for row in rows:
        if row["split"]=="train":
            train_counts[row["task_type"],row["context_length_s"]][row["answer"]]+=1
            question_counts[row["task_type"],row["context_length_s"],row["question"]][row["answer"]]+=1
    scores=defaultdict(list);question_scores=defaultdict(list)
    for row in rows:
        if row["split"]=="train":continue
        prediction=train_counts[row["task_type"],row["context_length_s"]].most_common(1)[0][0]
        scores[row["split"],row["task_type"]].append(evaluate(row["answer"],prediction,row["answer_type"])["correct"])
        counter=question_counts.get((row["task_type"],row["context_length_s"],row["question"]))
        query_prediction=counter.most_common(1)[0][0] if counter else prediction
        question_scores[row["split"],row["task_type"]].append(evaluate(row["answer"],query_prediction,row["answer_type"])["correct"])
    result=dict(self_score={s:{k:counts[s,k] for k in ("ok","failed")} for s in ("train","validation","test")},
                failures=failures,localization_position_mismatches=position_errors,
                coordinate_endpoint_oracle=dict(train_n=len(coordinate_outputs),accuracy=sum(coordinate_outputs)/len(coordinate_outputs),
                    meaning="零信号下，特权端点坐标仍可重建答案；这不是训练模型成绩，也不证明模型已使用该捷径"),
                train_majority_baseline=[dict(split=s,task=t,n=len(values),accuracy=sum(values)/len(values),
                    question_only_accuracy=sum(question_scores[s,t])/len(values)) for (s,t),values in sorted(scores.items())])
    relative_files=["src/datasets/uk_dale_haystack/loader.py","src/datasets/uk_dale_haystack/plot_generator.py",
        "src/datasets/uk_dale_haystack/core/background_sampler.py","src/datasets/uk_dale_haystack/core/insertion.py",
        "src/datasets/uk_dale_haystack/core/prompt_templates.py","src/datasets/capture24_haystack/utils/answer_evaluation.py",
        "src/datasets/capture24_haystack/utils/timestamp_utils.py"]
    result["official_source_sha256"]={p:hashlib.sha256((OFFICIAL/p).read_bytes()).hexdigest() for p in relative_files}
    (HERE/"semantic_checks.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k not in ("train_majority_baseline","official_source_sha256")},ensure_ascii=False))


if __name__=="__main__":main()
