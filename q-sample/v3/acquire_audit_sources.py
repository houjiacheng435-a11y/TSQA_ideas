"""只补齐审计所需目录元数据和少量训练 CSV，优先复用本地数据。"""
import argparse
import hashlib
import json
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
SOURCES = HERE / "sources"
TASKS = ("Shape Identification", "Temporal Localization", "Interval Discovery")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=HERE.parents[2])
    parser.add_argument("--cache", type=Path, default=HERE.parents[2] / "data/qsample-nlqts-audit")
    args = parser.parse_args()
    # 目录 API 分页必须取完，否则测试集尾部文件会被漏审。
    for name in ("NLQTSBench", "NLQTSBench-train", "NLQTSBench-train-v2"):
        api = json.loads((SOURCES / f"{name}-api.json").read_text())
        tree_path = SOURCES / f"{name}-tree.json"
        tree = json.loads(tree_path.read_text())
        if len([x for x in tree if x["path"].endswith(".csv")]) != len([x for x in api["siblings"] if x["rfilename"].endswith(".csv")]):
            url = f'https://huggingface.co/api/datasets/mrtan/{name}/tree/{api["sha"]}?recursive=true&limit=1000'
            tree = []
            while url:
                response = requests.get(url, timeout=60)
                response.raise_for_status()
                tree.extend(response.json())
                url = response.links.get("next", {}).get("url")
            tree_path.write_text(json.dumps(tree, indent=2))
    local = {}
    by_blob = {}
    for path in args.workspace.rglob("*.csv"):
        local.setdefault(path.name, path)
        data = path.read_bytes()
        oid = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        by_blob.setdefault(oid, path)
    jobs = []
    for name, filename, prefix in (("NLQTSBench-train", "NLQTSBench-train-tasks.json", ""), ("NLQTSBench-train-v2", "train-v2-general-tasks.json", "general/")):
        tasks = json.loads((SOURCES / filename).read_text())
        for subtask in TASKS:
            # 固定按 ID 取两题，不按波形、标签或方法分数挑样本。
            for task in sorted((x for x in tasks if x["subtask"] == subtask), key=lambda x: x["id"])[:2]:
                jobs.append((name, prefix, task))

    def fetch(job):
        name, prefix, task = job
        sha = json.loads((SOURCES / f"{name}-api.json").read_text())["sha"]
        relative = prefix + task["ts_data_path"]
        tree = json.loads((SOURCES / f"{name}-tree.json").read_text())
        expected_oid = next(x["oid"] for x in tree if x["path"] == relative)
        # 同一 CSV 可以被不同题号引用，必须按内容复用，不能只看文件名。
        path = by_blob.get(expected_oid)
        reused = path is not None
        url = f"https://huggingface.co/datasets/mrtan/{name}/resolve/{sha}/{relative}"
        if path is None:
            path = args.cache / name / relative
            if not path.exists():
                response = requests.get(url, timeout=90)
                response.raise_for_status()
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(response.content)
            data = path.read_bytes()
            oid = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            if oid != expected_oid:
                raise ValueError(f"官方 CSV 指纹不匹配：{task['id']}")
            by_blob[oid] = path
        record = dict(dataset=name, id=task["id"], path=str(path), url=url, reused=reused,
                      bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        print(task["id"], record["bytes"], "复用" if reused else "补齐", flush=True)
        return record

    # 顺序处理别名，保证本轮刚取回的同指纹文件也能直接复用。
    records = [fetch(job) for job in jobs]
    (HERE / "acquisition.json").write_text(json.dumps(records, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
