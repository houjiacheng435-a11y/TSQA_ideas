"""固定小规模官方样本清单，复用重建缓存；不改变官方问题、答案和划分。"""
import argparse
import concurrent.futures
import hashlib
import json

import pyarrow.parquet as pq
import requests

from paths import CACHE,HERE,TEXT_DIR,TEXT_REVISION
from source_io import reconstruct


def metadata(split,context,task):
    relative=f"tasks/{context}s/{task}/{split}/data.parquet"
    rows=[]
    for i,row in enumerate(pq.read_table(CACHE/relative).to_pylist()):
        if row["is_valid"]:
            row["row_id"]=relative+"#"+str(i)
            rows.append(row)
    return rows


def fixed_order(rows):
    return sorted(rows,key=lambda r:hashlib.sha256(("qsample-v5-seed7:"+r["row_id"]).encode()).hexdigest())


def make_plan():
    safe=set(json.loads((HERE/"sources/source_safe_row_ids.json").read_text()))
    groups={s:[] for s in ("train","validation","test","overfit","smoke","robust_validation","robust_test","long_train","long_validation","long_test")}
    for split,n in (("train",16),("validation",8),("test",8)):
        for ctx in (7200,32400):
            for task in ("existence","localization"):
                ordered=fixed_order(metadata(split,ctx,task))
                groups[split]+=ordered[:n]
                if split=="train":groups["overfit"]+=ordered[:8]
                else:groups["robust_"+split]+=[r for r in ordered if r["row_id"] in safe][:4]
        for task in ("existence","localization"):
            groups["long_"+split]+=fixed_order(metadata(split,86400,task))[:8 if split=="train" else 4]
    for ctx in (900,3600,7200):
        for task in ("existence","localization"):
            groups["smoke"].append(metadata("train",ctx,task)[0])
    for values in groups.values():
        for row in values:row["source_week_safe"]=row["row_id"] in safe
    document=dict(selection="按 seed7+row_id 的 SHA256 排序，按划分/长度/任务固定数量，不依据答案或性能筛选",groups=groups,
                  counts={k:len(v) for k,v in groups.items()},test_exposure="v4 已审计所有官方测试元数据；v5 不以测试选模型或超参数")
    path=HERE/"data_plan.json"
    if path.exists():assert json.loads(path.read_text())==document,"不覆盖不同的冻结样本方案"
    else:path.write_text(json.dumps(document,ensure_ascii=False,indent=2))
    print(document["counts"],flush=True)
    return document


def download_text():
    TEXT_DIR.mkdir(parents=True,exist_ok=True)
    def fetch(name):
        path=TEXT_DIR/name
        if not path.exists():
            url=f"https://huggingface.co/prajjwal1/bert-tiny/resolve/{TEXT_REVISION}/{name}"
            temporary=path.with_suffix(".tmp")
            for attempt in range(4):
                try:
                    with requests.get(url,timeout=60,stream=True) as response:
                        response.raise_for_status()
                        with temporary.open("wb") as handle:
                            for chunk in response.iter_content(1024*1024):handle.write(chunk)
                    assert temporary.stat().st_size==int(response.headers.get("Content-Length",temporary.stat().st_size))
                    temporary.replace(path)
                    break
                except (requests.RequestException,AssertionError):
                    if attempt==3:raise
        return dict(name=name,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        records=list(pool.map(fetch,("config.json","vocab.txt","pytorch_model.bin")))
    (HERE/"results/text_acquisition.json").write_text(json.dumps(dict(revision=TEXT_REVISION,files=records),indent=2))
    print("冻结文本编码器文件就绪",flush=True)


def ensure_metadata():
    """全新缓存只补齐两任务的轻量parquet，已有文件先校验再复用。"""
    from paths import REVISION
    tree=json.loads((HERE/"sources/hf-tree.json").read_text())
    jobs=[r for r in tree if r["path"]=="bout_index.parquet" or
          (r["path"].endswith("data.parquet") and r["path"].split("/")[2] in ("existence","localization"))]
    def fetch(record):
        path=CACHE/record["path"]
        if not path.exists():
            url=f"https://huggingface.co/datasets/nz00shuuuu/uk-dale-haystack/resolve/{REVISION}/{record['path']}"
            response=requests.get(url,timeout=60);response.raise_for_status()
            path.parent.mkdir(parents=True,exist_ok=True)
            temporary=path.with_suffix(".tmp");temporary.write_bytes(response.content);temporary.replace(path)
        payload=path.read_bytes();assert len(payload)==record["size"]
        if "lfs" in record:assert hashlib.sha256(payload).hexdigest()==record["lfs"]["oid"]
        else:assert hashlib.sha1(b"blob "+str(len(payload)).encode()+b"\0"+payload).hexdigest()==record["oid"]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(fetch,jobs))
    print(f"两任务元数据校验完成：{len(jobs)}文件",flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--groups",nargs="+",default=["train","validation","smoke","robust_validation"]);parser.add_argument("--text",action="store_true");parser.add_argument("--workers",type=int,default=6);parser.add_argument("--metadata",action="store_true")
    args=parser.parse_args()
    if args.metadata:ensure_metadata()
    plan=make_plan()
    if args.text:download_text()
    rows={r["row_id"]:r for group in args.groups for r in plan["groups"][group]}
    outcomes=reconstruct(list(rows.values()),max_workers=args.workers)
    if any(row["status"]!="ok" for row in outcomes):raise SystemExit("存在下载失败；保持样本清单不变，重新运行补齐缓存")
