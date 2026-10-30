#!/usr/bin/env bash
set -euo pipefail
# Override these absolute paths when reproducing on another server.
V016_PYTHON=${V016_PYTHON:-/root/v016-sonarts-env/bin/python}
V016_MODEL=${V016_MODEL:-/root/autodl-tmp/cf-run/models/qwen3-8b}
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2
exec "$V016_PYTHON" -m vllm.entrypoints.openai.api_server \
  --model "$V016_MODEL" --served-model-name Qwen3-8B \
  --host 127.0.0.1 --port 8016 --dtype bfloat16 \
  --max-model-len 16384 --max-num-seqs 1 --gpu-memory-utilization 0.88 \
  --max-num-batched-tokens 2048 --enforce-eager \
  --generation-config vllm --disable-log-requests
