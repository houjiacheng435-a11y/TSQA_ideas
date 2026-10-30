# v016: Sonar-TS + Qwen3-8B

This is a local-backbone adaptation, not Sonar-TS's published DeepSeek result.
Upstream code: https://github.com/Atlamtiz/Sonar-TS (Apache-2.0), commit
`99866c43cd7ceb91a929de745e9f49cea92962e5`. The upstream source is unmodified.

## Environment and inputs

The existing environment has Python 3.12, torch 2.6.0+cu124,
torchvision 0.21.0+cu124, transformers 4.52.4. Create an isolated venv with
`python -m venv --system-site-packages /root/v016-sonarts-env`, then install
this directory's `requirements.txt` there. The exact imported environment is
recorded in the experiment artifacts. Do not upgrade the original environment.

Reuse the existing Qwen/Qwen3-8B weights, source revision
`b968826d9c46dd6066d109eabc6255188de91218`. No weight download is performed.
Reuse local NLQTSBench CSVs, dataset revision
`81571171c5c614d01698497626bff8eb6ad8dcf4`. `prepare.py` has ten fixed IDs;
the saved selection records CSV hashes. It only reads the CSVs and writes new
SQLite databases and official offline features. Missing inputs cause failure,
rather than silently changing the selection or downloading the full dataset.

Commands below assume the repository is `/root/autodl-tmp/cf-run/TSQA_ideas`.
Set `V016_CODE`, `V016_OFFICIAL`, and `V016_OUT` to absolute paths when moving.
Never point `V016_OUT` at a prior experiment; preparation uses exclusive writes.

```bash
V016_CODE=/root/autodl-tmp/cf-run/TSQA_ideas/complementary-ts-retrieval/experiments/v016-sonarts-qwen-local
V016_OFFICIAL=/root/autodl-tmp/cf-run/vendor/Sonar-TS-v016-minimal
V016_OUT=/root/autodl-tmp/cf-run/TSQA_ideas/complementary-ts-retrieval/results/v016-sonarts-qwen-local
V016_PY=/root/v016-sonarts-env/bin/python

# Clone upstream separately, then checkout the pinned commit.
# git clone https://github.com/Atlamtiz/Sonar-TS.git "$V016_OFFICIAL"
# git -C "$V016_OFFICIAL" checkout 99866c43cd7ceb91a929de745e9f49cea92962e5

"$V016_PY" "$V016_CODE/prepare.py" --official "$V016_OFFICIAL" \
  --project /root/autodl-tmp/cf-run/TSQA_ideas/complementary-ts-retrieval --out "$V016_OUT"
"$V016_PY" "$V016_CODE/check_trace.py" --official "$V016_OFFICIAL" --out "$V016_OUT"

# Run in a dedicated terminal; bind only to loopback. No external API or API key.
bash "$V016_CODE/serve.sh"

# In another terminal, same path variables. Run smoke first; inspect its complete
# task trace and final output before invoking pilot10. pilot10 enforces this gate
# and reuses the smoke task rather than repeating its inference.
"$V016_PY" "$V016_CODE/run.py" --official "$V016_OFFICIAL" --out "$V016_OUT" --phase smoke
"$V016_PY" "$V016_CODE/run.py" --official "$V016_OFFICIAL" --out "$V016_OUT" --phase pilot10
"$V016_PY" "$V016_CODE/summarize.py" --out "$V016_OUT"

# Official evaluation CLI (sequential numeric IDs refer to tasks-selected order).
cd "$V016_OFFICIAL"
"$V016_PY" -m sonar_ts.evaluator --tasks "$V016_OUT/tasks-selected.json" \
  --predict "$V016_OUT/pilot10/predict.json" \
  --out-summary "$V016_OUT/official-summary.json" \
  --out-per-task "$V016_OUT/official-per-task.json"

"$V016_PY" "$V016_CODE/audit_run.py" --out "$V016_OUT"
"$V016_PY" "$V016_CODE/environment.py" --official "$V016_OFFICIAL" \
  --model /root/autodl-tmp/cf-run/models/qwen3-8b --out "$V016_OUT/environment-verified.json"
# After stopping the local server (so logs are complete), export the small
# GitHub artifacts; this creates a fresh artifacts directory, never merges it.
"$V016_PY" "$V016_CODE/export_artifacts.py" --out "$V016_OUT" --dest "$V016_OUT/published-artifacts"
```

## What changes

`run.py` injects a duck-typed LLM client into the official `pipeline.run_task`.
It changes only the endpoint/backbone/template kwargs and adds measurements:
greedy (`temperature=0`), 4096 output tokens, Qwen `enable_thinking=false`,
600-second local HTTP timeout. Planning, skill selection, prompts, code
extraction, three regeneration opportunities, 60-second execution timeout,
shape validation, deterministic answer formatting and evaluation remain upstream.

`traced_runner.py` wraps the upstream runner. It logs executed SQL, all returned
SQL result rows, and final generated-program variables; SQLite opens are made
read-only, as the upstream prompt promises. `check_trace.py` checks an actual
query produces the same stdout with and without this instrumentation. This log
contains numerical raw slices, so the large SQL logs remain on the server.
The logging overhead is included in task wall time and execution timeout.

No new learned retriever is trained, no paid model is called, no global
benchmark is started, and the upstream skill library is retained (including
its benchmark-specific numerical recipes). A successful process exit means
execution/shape success, not semantic correctness or sufficient evidence.

## Traces

Each task directory contains `llm-calls.jsonl` (complete prompts/responses and
token usage), `code-N.py`, `execution-N.json` (stdout/stderr/result/status),
`sql-N.jsonl.gz` (SQL/candidates/variables), `gpu-samples.json`, and `record.json`.
`pilot10/records.json` aggregates results. `selection.json`, `offline-config.json`,
`environment-verified.json`, both phase run configs, and artifact hashes record provenance.
The verified environment resolves duplicate base/venv packages by import priority;
older inventory snapshots remain on the server and are not authoritative version locks.
GPU memory is sampled process-resident usage from nvidia-smi, including the
preallocated vLLM KV cache; it is not per-task incremental tensor allocation.
