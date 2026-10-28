"""为本地下载的 ChatTS 权重创建本项目所需的来源清单。

原始 realtime-tslm 的加载器不会直接接受一个来源未知的模型目录，而是要求目录内
有 ``relay-manifest.json``。本脚本在 AutoDL 下载完官方固定版本的 ChatTS-8B 后运行，
把每个文件的大小和 SHA-256 写入该清单，方便后续复核。它不会下载、修改或删除模型权重。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


REPO_ID = "bytedance-research/ChatTS-8B"
REVISION = "7216a84034063c2d394901fe45d20a1e8d773a1f"
MANIFEST_NAME = "relay-manifest.json"


def sha256(path: Path) -> str:
    """分块计算文件摘要，避免一次性把大权重读入内存。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(model_dir: Path, repo_id: str, revision: str) -> dict:
    if not model_dir.is_dir():
        raise FileNotFoundError(f"模型目录不存在：{model_dir}")

    files = [
        path
        for path in sorted(model_dir.rglob("*"))
        if path.is_file() and path.name != MANIFEST_NAME and ".cache" not in path.parts
    ]
    if not files:
        raise ValueError(f"模型目录为空：{model_dir}")

    # 权重索引或任意 safetensors/bin 权重至少要有一种，防止误对空目录生成清单。
    has_weights = any(
        path.suffix in {".bin", ".safetensors"} or path.name.endswith(".index.json")
        for path in files
    )
    if not has_weights:
        raise ValueError("未发现模型权重或权重索引；请先执行 hf download。")

    return {
        "repo_id": repo_id,
        "revision": revision,
        "purpose": "Local ChatTS model provenance and integrity record.",
        "files": [
            {
                "path": path.relative_to(model_dir).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in files
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="创建 ChatTS 本地权重来源清单")
    parser.add_argument("--model-dir", type=Path, required=True, help="ChatTS-8B 本地目录")
    parser.add_argument("--repo-id", default=REPO_ID)
    parser.add_argument("--revision", default=REVISION)
    parser.add_argument("--overwrite", action="store_true", help="覆盖已有的 relay-manifest.json")
    args = parser.parse_args()

    output = args.model_dir / MANIFEST_NAME
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"清单已存在：{output}；确认后可加 --overwrite 覆盖。")

    manifest = build_manifest(args.model_dir, args.repo_id, args.revision)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已写入 {output}（记录 {len(manifest['files'])} 个文件）。")


if __name__ == "__main__":
    main()
