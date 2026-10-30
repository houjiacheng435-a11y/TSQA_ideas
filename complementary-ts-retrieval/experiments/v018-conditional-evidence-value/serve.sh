#!/usr/bin/env bash
set -euo pipefail
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2
exec /root/v016-sonarts-env/bin/python -m vllm.entrypoints.openai.api_server \
 --model /root/autodl-tmp/cf-run/models/qwen3-8b --served-model-name Qwen3-8B \
 --host 127.0.0.1 --port 8018 --dtype bfloat16 --max-model-len 8192 \
 --max-num-seqs 4 --gpu-memory-utilization 0.88 --max-num-batched-tokens 2048 \
 --enforce-eager --generation-config vllm --disable-log-requests
