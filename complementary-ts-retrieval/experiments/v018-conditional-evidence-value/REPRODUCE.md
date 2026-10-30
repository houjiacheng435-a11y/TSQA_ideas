# v018 reproduction notes

This directory is separate from v001–v017. The study tests a controlled clock-calibrated response-phase task; it is not an official Sonar-TS evaluation. No training or external API is used. Read the Chinese report before interpreting a weak baseline as a general retrieval failure.

## Existing machine

Working directory: `/root/autodl-tmp/cf-run`.
Python: `/root/v016-sonarts-env/bin/python` (Python 3.12.3, torch 2.6.0+cu124, transformers 4.52.4, vLLM 0.8.5.post1, NumPy 1.26.4).
Local checkpoints: `models/qwen3-8b` and `models/chatts-8b`. Configuration hashes and byte sizes are in the artifact environment record. ChatTS uses its existing `relay-manifest.json` and trusted checkpoint code. The frozen 93-line runtime is byte-identical to the existing local implementation.

The programs derive their output directory from their location: `../../results/v018-conditional-evidence-value/`. Completed files are created exclusively. **Do not rerun into the completed server directory.** Use a fresh checkout/workspace with the same relative layout and existing model directories. No program downloads weights.

## Order of execution in a fresh workspace

Run each command separately, from this directory, using the Python environment above:

```bash
python build.py
python cpu.py
python ablations.py
python counterfactual_metrics.py
```

`audit.complete.json` must contain `gpu_gate_passed=true` before any model command will run. `protocol.json` predates outcomes. The task generator, all counterfactual worlds and seeds are deterministic. The `train` split is reserved and audited; it is not used for model training. MMR's coefficient is selected using the development split, then held fixed.

Start the server in a separate terminal (review paths in `serve.sh` if your layout differs):

```bash
bash serve.sh
```

Wait until `http://127.0.0.1:8018/v1/models` lists Qwen3-8B. Then run:

```bash
python gpu.py --stage agents --workers 4
python gpu.py --stage agents --workers 4 --documented-rules
python gpu.py --stage agents --workers 2 --documented-rules --neutral-stop-example
python gpu.py --stage readers --workers 4
python gpu.py --stage lag-control --workers 2
```

The first two conditions have 960 fixed episodes each. The supplementary neutral-example condition has the 288 fixed full-reader cases as dynamic episodes; it does not have paired initial-source contexts and must not be given an initial-context action-flip score. The readers stage makes 864 calls: raw first action, raw full-certificate reading and decoded-phase reading.

A supplementary lag-control makes another 288 calls: a fixed tool provides the corrected true delay from the acquired full certificate and explicitly states that evidence is complete. It diagnoses the combined arithmetic/tool-semantic interface; it is not retrieval performance or a pure arithmetic-only ablation. This condition was added after observing full-evidence abstentions, with all earlier results preserved.

Stop **only the Qwen server you started**, using Ctrl-C in its terminal. Ensure it has released GPU memory before loading ChatTS:

```bash
python native.py
python score_gpu.py
```

`native.py` performs 576 greedy ChatTS calls (288 native time-series and 288 numerical-fact controls). It checks one `<ts><ts/>` placeholder per input series. Qwen uses BF16, non-thinking mode and constrained JSON; ChatTS uses its already-tested FP16 runtime and unconstrained greedy output. The numerical extraction rule and exact verifier are separately scored; their success is not credited to an LLM.

## Provenance and supplementary conditions

The earliest interface prototype used a literal `FETCH|STOP` example that the model copied. That run was interrupted, retained on the server and excluded. The evaluated reference instead uses a JSON Schema with legal candidate IDs and budget constraints. These constraints guarantee only action syntax/budget validity, not correct selection or stopping.

A concrete UNKNOWN stop example remains in the reference prompt. After inspecting this interface and early reference behavior, we added the documented-rule condition and then a neutral-example condition. They are **supplementary diagnostic controls**, not preregistered independent replications. Both earlier outcomes remain visible. The neutral condition removes only the concrete UNKNOWN demonstration, leaving the documented physical/tool rules intact. Exact original reference/documented source snapshots are archived: their config hashes differ from the final CLI source because the latter adds these optional controls. Use snapshots if byte-identical historical requests are needed; complete actual requests are also archived.

The initial audit compared public states with different remaining budgets (4 versus 3) and failed an assertion. We corrected that audit setup, verified that existing immutable generated families/protocol were unchanged, then completed all necessity checks before GPU access. Both initial and successful audit logs are archived. No task was rejected or relabelled to fix this assertion.

The main CPU methods/protocol were not replaced after seeing their scores. Supplementary tie-breaking/public-bound comparisons are explicitly marked in `supplementary-ablations.json`.

## CPU-only verification of published results

The published archives include generated synthetic family parameters, fixed episode lists, CPU trajectories/aggregates, all evaluated model records and actual API requests/responses. Evaluation-only labels must never be passed as agent observations. The broker constructs public observations using only index previews and acquired records.

```bash
python verify_artifacts.py
```

This verifies the archive manifest and replays every evaluated dynamic retrieval through the broker, without GPU inference, changing data or extracting archives onto the original result directory. Large pre-existing NLQTSBench files, model weights, environment caches and credentials are excluded. Full raw server results are retained at the path above.
