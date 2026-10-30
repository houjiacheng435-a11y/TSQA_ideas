# v017 reproduction and interpretation

Use the existing v016 Python environment and local weights. No downloads or
training are required. These scripts create new v017 outputs with exclusive
writes; do not rerun into an existing result path. For a fresh reproduction,
use a separate repository checkout/result namespace. Prior v015/v016 files
are read only.

```bash
V017_PY=/root/v016-sonarts-env/bin/python
V017_CODE=/root/autodl-tmp/cf-run/TSQA_ideas/complementary-ts-retrieval/experiments/v017-conditional-complementary-retrieval
V017_SONAR=/root/autodl-tmp/cf-run/vendor/Sonar-TS-v016-minimal
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
"$V017_PY" "$V017_CODE/build_and_audit.py"
"$V017_PY" "$V017_CODE/fixed_v016.py" --official "$V017_SONAR"
"$V017_PY" "$V017_CODE/check_boundary.py"
# Inspect CPU audit and all four fixed-program outputs before enabling GPU.
# Serve using the v016 serve.sh (loopback, BF16, non-thinking request kwargs).
```

`pilot.py` is an explicitly adapted Sonar-TS *protocol precheck*, not a valid
original Sonar-TS method reproduction. It imports upstream `planner.plan`,
`generator.generate` and `generator.regenerate`, uses new prompt paths, and
replaces SQL execution with the restricted broker. Original source, prompt
files, skill library and old results are never edited. The original SAX search
and original task skills do not map directly to this task's access constraints.

The observed precheck was stopped after four completed episodes and part of a
fifth, when interface limits and placeholder programs made the comparison
unfair. One observed error was that the DSL did not expose `next`; do not count
this as a model/retrieval defect. Remaining logs are preserved, not imputed or
silently replaced. Do **not** rerun all 20 adapter episodes to claim that
Sonar-TS fails, and do not treat generated placeholders as functioning search.

The validated small GPU experiment is `controls.py`: all 20 preselected episodes
(families 1 and 6, no swaps) use the simple state rule to collect evidence.
Qwen independently evaluates initial and acquired raw observations. No verifier
answer, hidden label or private pool is in these prompts. Four zero-fetch cases
reuse the identical initial judgment, so there are 36 API calls for 40 scored
states. No generations are reused across different inputs.

```bash
"$V017_PY" "$V017_CODE/controls.py"
"$V017_PY" "$V017_CODE/score.py"
# Stop the vLLM service after the control completes, then publish small files.
# publish.py creates a fresh artifacts directory, never overwrites it.
# On a cloned repository, choose a new output destination before publishing;
# the committed artifacts are already the original observation record.
```

Task semantics are in `task.py`. A 42-point complete target trace is paired to
the requested episode by its eight content-context values, not its name/time.
Preview indices contain four context values, no pulse onset or answer. The
three candidates with a given target channel share identical clock metadata.
One is useful, one belongs to another episode, and one has similar context.
There are also irrelevant channels and the initial target's redundant record.
The condition is a conjunction: both targets must pulse, and the second onset
must be exactly two samples later. A complete no-pulse target settles NO, so
not every episode needs another retrieval or always needs the same channel.

The restricted child process receives public inputs and a pipe, no private pool
or label. AST checks block imports, filesystem access, introspection, and
unsupported attributes. Only broker `index/fetch/verify` can access evidence;
successful fetches are charged and retained across retries. This is a limited
diagnostic DSL, not a claim of general adversarial Python isolation.

CPU baselines share the same index, budget and exact verifier. Independent
relevance scores a candidate by target relevance and context distance, without
conditioning on already-covered channels. Coverage adds a missing-target bonus;
the state rule explicitly identifies the missing target then matches context.
They are different implementations but effectively equivalent in this easy task.
Oracle privately chooses the unique useful record and is only an upper bound.

The exact verifier controls CPU stopping. Therefore those methods' perfect
sufficiency judgments are supplied tool behavior, not learned judgment ability.
Qwen's own sufficiency/answer metrics are computed separately. `scores.json`
reports both layers and counterfactual pairs. 640 CPU episodes include eight
order rotations of 80 world/initial states across eight synthetic families;
they are not 640 independent natural questions.

Server directory `results/v017-conditional-complementary-retrieval/` retains
every CPU candidate selection, obtained record, state verification, stopping
outcome, complete model request/response and excluded precheck. Git artifacts
include small scores/configs and gzip model traces, not large raw NLQTSBench
data or the 5120-trajectory CPU dump. `pilot-evaluation-only.json.gz` includes
ground truth and must never be used as a retriever's input.
