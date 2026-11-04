"""只取预先选定训练题的信号字节窗口，做同预算波形保留诊断，不训练模型。"""
import ast
import concurrent.futures
import hashlib
import json
import os
import threading
from pathlib import Path

import numpy as np
import requests

from acquire_metadata import CACHE, HERE, REVISION, SOURCE

OFFICIAL = Path(os.environ.get("TS_HAYSTACK_SOURCE", "/root/autodl-tmp/cf-run/vendor/v020/TS-Haystack"))
BLOCK = 2048
RAW = CACHE / "range_cache"
LOCK = threading.RLock()
RECORDS = {}
METERS = {}


def byte_range(relative, start, stop):
    """拒绝忽略 Range 的响应，避免无意下载整个信号库；区间右端不包含。"""
    key = f"{relative}:{start}:{stop}"
    filename = RAW / (hashlib.sha256(key.encode()).hexdigest() + ".bin")
    if not filename.exists():
        url = f"https://huggingface.co/datasets/nz00shuuuu/uk-dale-haystack/resolve/{REVISION}/{relative}"
        error = None
        for _ in range(3):
            try:
                with requests.get(url, params={"audit_range": f"{start}-{stop-1}"},
                                  headers={"Range": f"bytes={start}-{stop-1}"},
                                  timeout=40, stream=True) as response:
                    if response.status_code != 206:
                        raise ValueError(f"Range 未生效：{relative} {response.status_code}")
                    expected = f"bytes {start}-{stop-1}/"
                    if not response.headers.get("Content-Range", "").startswith(expected):
                        raise ValueError("Content-Range 与请求不符")
                    data = response.raw.read(stop-start+1)
                    assert len(data) == stop-start
                RAW.mkdir(parents=True, exist_ok=True)
                temporary = filename.with_suffix(f".{threading.get_ident()}.tmp")
                temporary.write_bytes(data)
                temporary.replace(filename)
                break
            except (requests.RequestException, ValueError, AssertionError) as exc:
                error = exc
        else:
            raise error
    data = filename.read_bytes()
    assert len(data) == stop-start
    with LOCK:
        RECORDS[key] = dict(path=relative, start=start, stop=stop, bytes=len(data),
                            sha256=hashlib.sha256(data).hexdigest())
    return data


class Meter:
    def __init__(self, house, meter):
        self.prefix = f"signals/h{house}/m{meter}"
        self.blocks = {}
        self.headers = {}

    def header(self, suffix):
        if suffix not in self.headers:
            raw = byte_range(self.prefix+suffix, 0, 128)
            assert raw[:8] == b"\x93NUMPY\x01\x00"
            length = int.from_bytes(raw[8:10], "little")
            assert length+10 == 128
            info = ast.literal_eval(raw[10:128].decode().strip())
            assert not info["fortran_order"] and len(info["shape"]) == 1
            self.headers[suffix] = (np.dtype(info["descr"]), info["shape"][0])
        return self.headers[suffix]

    def array(self, suffix, lo, hi):
        dtype, n = self.header(suffix)
        assert 0 <= lo <= hi <= n
        if lo == hi:
            return np.empty(0, dtype=dtype)
        return np.frombuffer(byte_range(self.prefix+suffix, 128+lo*dtype.itemsize,
                                        128+hi*dtype.itemsize), dtype=dtype).copy()

    def block(self, index):
        _, n = self.header(".t.npy")
        if index not in self.blocks:
            block = self.array(".t.npy", index*BLOCK, min(n, (index+1)*BLOCK))
            assert np.all(np.diff(block) >= 0)
            with LOCK:
                self.blocks[index] = block
        return self.blocks[index]

    def lower_bound(self, timestamp):
        _, n = self.header(".t.npy")
        n_blocks = (n+BLOCK-1)//BLOCK
        self.block(0)
        self.block(n_blocks-1)
        for _ in range(40):
            with LOCK:
                known = sorted(self.blocks.items())
            lo, hi = 0, n_blocks-1
            for index, block in known:
                if block[0] <= timestamp <= block[-1]:
                    return index*BLOCK + int(np.searchsorted(block, timestamp))
                if block[-1] < timestamp:
                    lo = max(lo, index)
                if block[0] > timestamp:
                    hi = min(hi, index)
            if timestamp <= self.block(0)[0]:
                return 0
            if timestamp > self.block(n_blocks-1)[-1]:
                return n
            if hi-lo == 1:
                return hi*BLOCK
            # 时间插值只用于定位原文件索引，不对原始波形做插值或扩长。
            fraction = (timestamp-int(self.block(lo)[-1])) / (int(self.block(hi)[0])-int(self.block(lo)[-1]))
            index = int(np.clip(round(lo+(hi-lo)*fraction),lo+1,hi-1))
            self.block(index)
        raise RuntimeError("时间戳索引未收敛")

    def window(self, start, end):
        lo, hi = self.lower_bound(start), self.lower_bound(end)
        return self.array(".t.npy",lo,hi), self.array(".npy",lo,hi)


def official_function(relative, name, namespace):
    """执行固定官方代码中的原函数，避开整个框架的重型依赖。"""
    source = (OFFICIAL/relative).read_text()
    node = next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name==name)
    code = ast.Module(body=[node], type_ignores=[])
    exec(compile(code,str(OFFICIAL/relative),"exec"),namespace)
    return namespace[name]


def reconstruct(rows):
    loader = "src/datasets/uk_dale_haystack/loader.py"
    resample = official_function(loader,"resample_to_grid",dict(np=np,NOMINAL_DT_S=6.0))
    manifest = json.loads((SOURCE/"manifest.json").read_text())
    def load_grid(house,meter,start,end,dt_s=6.0):
        with LOCK:
            obj = METERS.setdefault((house,meter),Meter(house,meter))
        ts, values = obj.window(start-int(2*dt_s*1e9),end)
        return resample(ts,values,start,end,dt_s)
    namespace = dict(np=np,json=json,Any=object,
                     load_meter_window_grid=load_grid,
                     mains_meter_id=lambda h:int(manifest["houses"][str(h)]["mains_meter"]))
    function = official_function("src/datasets/uk_dale_haystack/plot_generator.py",
                                 "reconstruct_sample_signal",namespace)
    output = CACHE/"reconstructed"
    output.mkdir(parents=True,exist_ok=True)
    def process(row):
        filename = output/(hashlib.sha256(row["row_id"].encode()).hexdigest()+".npy")
        try:
            if not filename.exists():
                signal = function(row)
                assert len(signal)==round(row["context_length_s"]/row["dt_s"])
                assert signal.dtype == np.float32 and np.isfinite(signal).all()
                np.save(filename,signal)
            signal = np.load(filename)
            result = dict(row_id=row["row_id"],status="ok",path=str(filename),samples=len(signal),
                          sha256=hashlib.sha256(filename.read_bytes()).hexdigest(),
                          min_w=float(signal.min()),max_w=float(signal.max()))
        except Exception as exc:
            result = dict(row_id=row["row_id"],status="failed",error=f"{type(exc).__name__}: {exc}")
        print(json.dumps(result,ensure_ascii=False),flush=True)
        return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        outcomes = list(executor.map(process,rows))
    provenance_path=HERE/"signal_acquisition.json"
    previous=json.loads(provenance_path.read_text()) if provenance_path.exists() else {}
    ranges={(r["path"],r["start"],r["stop"]):r for r in previous.get("ranges",[])}
    ranges.update({(r["path"],r["start"],r["stop"]):r for r in RECORDS.values()})
    provenance_path.write_text(json.dumps(dict(
        revision=REVISION,results=outcomes,ranges=sorted(ranges.values(),key=lambda x:(x["path"],x["start"])),
        unique_bytes=sum(x["bytes"] for x in ranges.values())),ensure_ascii=False,indent=2))
    return outcomes


if __name__=="__main__":
    reconstruct(json.loads((HERE/"selected_train_rows.json").read_text()))
