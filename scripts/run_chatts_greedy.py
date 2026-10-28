#!/usr/bin/env python3
"""在新反事实集上运行 ChatTS 的单卡、逐题贪心推理。

这是新项目的推理入口，不修改旧项目中用于复现历史论文数字的脚本。它复用旧
项目经过验证的 ``runtime.py`` 完成模型加载、时序编码和逐 token 贪心解码。
输出保存原始回复、解析出的选项和耗时；本脚本不把耗时当作跨机器可比的结论。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cf_ts.choice_parser import parse_choice_index  # noqa: E402

DEFAULT_INPUT = ROOT / "data" / "generated" / "inference_input.jsonl"
DEFAULT_PROJECT = ROOT.parent / "realtime-tslm"


def sha256_file(path: Path) -> str:
    """计算输入、脚本和结果的文件哈希，便于服务器回收后追溯。"""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path: Path):
    """读取输入题目。"""

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path} 的第 {line_number} 行不是有效 JSON") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True, help="本地 ChatTS 模型目录；需含旧项目要求的 relay-manifest.json")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--realtime-project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--max-new-tokens", type=int, default=128)
    parser.add_argument("--limit", type=int, default=None, help="仅运行前 N 条，用于冒烟测试")
    args = parser.parse_args()
    if args.max_new_tokens < 1:
        raise ValueError("--max-new-tokens 必须为正数")
    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit 必须为正数")
    if not args.input.is_file() or not args.model.is_dir():
        raise FileNotFoundError("--input 必须是文件，--model 必须是存在的模型目录")
    if not (args.realtime_project / "src" / "rt_tslm" / "runtime.py").is_file():
        raise FileNotFoundError("--realtime-project 中找不到 src/rt_tslm/runtime.py")
    if args.output.exists() or args.output.with_suffix(".meta.json").exists() or args.output.with_suffix(".complete.json").exists():
        raise FileExistsError("输出或其元数据已存在；请使用新的输出文件名，避免覆盖旧实验")

    # 旧项目依赖在服务器上准备好的、可离线读取的模型目录。这里不下载模型，
    # 也不在下载失败时静默回退到其他版本。
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    sys.path.insert(0, str(args.realtime_project / "src"))
    import numpy as np  # noqa: PLC0415
    import torch  # noqa: PLC0415
    from rt_tslm.choice_qa import choice_prompt  # noqa: PLC0415
    from rt_tslm.runtime import decode, expand_inputs, load_local, render_prompt, synchronize  # noqa: PLC0415

    rows = list(read_jsonl(args.input))
    if args.limit is not None:
        rows = rows[:args.limit]
    if not rows:
        raise ValueError("没有可运行的输入题目")
    identifiers = [row.get("id") for row in rows]
    if len(identifiers) != len(set(identifiers)) or any(not value for value in identifiers):
        raise ValueError("输入中每条题目必须有唯一且非空的 id")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.set_grad_enabled(False)
    model, tokenizer, processor = load_local(args.model, device=args.device)
    eos = model.generation_config.eos_token_id
    eos_ids = [eos] if isinstance(eos, int) else list(eos)
    started = time.time()
    records = 0
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        for position, row in enumerate(rows, 1):
            prompt = render_prompt(tokenizer, choice_prompt(row))
            channels = [np.asarray(values, dtype=float) for values in row["series"]]
            batch = processor(text=[prompt], timeseries=channels, padding=True, return_tensors="pt")
            batch = {key: value.to(args.device) for key, value in batch.items()}
            with torch.inference_mode():
                prepared = expand_inputs(model, batch)
                if prepared.embeddings.shape[1] + args.max_new_tokens > model.config.max_position_embeddings:
                    raise ValueError(f"{row['id']} 超出模型上下文长度")
                result = decode(model, prepared, max_new_tokens=args.max_new_tokens, eos_ids=eos_ids, use_cache=True)
            synchronize(args.device)
            answer = tokenizer.decode(result["tokens"], skip_special_tokens=True).strip()
            record = {
                "id": row["id"],
                "parent_id": row.get("parent_id", row["id"]),
                "expected_choice_index": row["answer_index"],
                "predicted_choice_index": parse_choice_index(answer, len(row["choices"])),
                "answer": answer,
                "tokens": result["tokens"],
                "stopped_on_eos": result["stopped_on_eos"],
                "prefill_ms": result["prefill_ms"],
                "decode_ms": result["decode_ms"],
                "counterfactual": row.get("counterfactual"),
            }
            handle.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
            handle.flush()
            records += 1
            print(json.dumps({
                "done": position,
                "total": len(rows),
                "id": row["id"],
                "predicted_choice_index": record["predicted_choice_index"],
                "stopped_on_eos": record["stopped_on_eos"],
            }, ensure_ascii=False), flush=True)

    metadata = {
        "complete": True,
        "records": records,
        "started_unix": started,
        "elapsed_seconds": time.time() - started,
        "input": str(args.input),
        "input_sha256": sha256_file(args.input),
        "output": str(args.output),
        "output_sha256": sha256_file(args.output),
        "script_sha256": sha256_file(Path(__file__)),
        "runtime_sha256": sha256_file(args.realtime_project / "src" / "rt_tslm" / "runtime.py"),
        "model": str(args.model),
        "device": args.device,
        "max_new_tokens": args.max_new_tokens,
        "limit": args.limit,
        "note": "单卡逐题贪心推理记录；跨机器、跨环境的耗时不可直接比较。",
    }
    args.output.with_suffix(".meta.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.output.with_suffix(".complete.json").write_text(
        json.dumps({"complete": True, "records": records, "output_sha256": metadata["output_sha256"]}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
