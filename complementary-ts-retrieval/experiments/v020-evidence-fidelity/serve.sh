#!/usr/bin/env bash
set -euo pipefail
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
exec /root/v016-sonarts-env/bin/python -m vllm.entrypoints.openai.api_server \
 --model /root/autodl-tmp/cf-run/models/qwen3-8b --served-model-name Qwen3-8B \
 --host 127.0.0.1 --port 8020 --dtype bfloat16 --max-model-len 16384 \
 --max-num-seqs 1 --gpu-memory-utilization 0.88 --max-num-batched-tokens 2048 \
 --enforce-eager --generation-config vllm --disable-log-requests
