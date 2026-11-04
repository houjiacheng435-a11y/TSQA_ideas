"""固定 revision，仅补齐轻量 QA 元数据，不下载完整信号侧车。"""
import concurrent.futures
import hashlib
import json
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "sources"
REVISION = json.loads((SOURCE / "hf-api.json").read_text())["sha"]
CACHE = HERE.parents[2] / "data/qsample-v4-ukdale" / REVISION


def main():
    tree = json.loads((SOURCE / "hf-tree.json").read_text())
    jobs = [x for x in tree if x["path"].endswith("data.parquet") or x["path"] == "bout_index.parquet"]
    def fetch(record):
        relative = record["path"]
        path = CACHE / relative
        reused = path.exists()
        url = f"https://huggingface.co/datasets/nz00shuuuu/uk-dale-haystack/resolve/{REVISION}/{relative}"
        if not reused:
            error = None
            for _ in range(3):
                try:
                    response = requests.get(url, timeout=60)
                    response.raise_for_status()
                    data = response.content
                    break
                except requests.RequestException as exc:
                    error = exc
            else:
                raise error
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        data = path.read_bytes()
        assert len(data) == record["size"], relative
        if "lfs" in record:
            assert hashlib.sha256(data).hexdigest() == record["lfs"]["oid"], relative
        else:
            assert hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest() == record["oid"], relative
        return dict(path=relative, local=str(path), url=url, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), reused=reused)
    # 分片只含文本与重建配方；全部合计约 13.5 MB，不包含波形数组。
    records = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as executor:
        futures = [executor.submit(fetch, job) for job in jobs]
        for future in concurrent.futures.as_completed(futures):
            records.append(future.result())
            if len(records) % 25 == 0:
                print(f"元数据进度：{len(records)}/{len(jobs)}", flush=True)
    records.sort(key=lambda record: record["path"])
    (HERE / "metadata_acquisition.json").write_text(json.dumps(records, ensure_ascii=False, indent=2))
    print(json.dumps(dict(files=len(records), bytes=sum(x["bytes"] for x in records), reused=sum(x["reused"] for x in records))))


if __name__ == "__main__":
    main()
