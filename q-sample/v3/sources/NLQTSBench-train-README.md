---
license: apache-2.0
language:
- en
task_categories:
- question-answering
- table-question-answering
tags:
- time-series
- natural-language-queries
- benchmark
- training-set
size_categories:
- n<1K
pretty_name: NLQTSBench-train
---

# NLQTSBench-train

Training-split companion to
[`mrtan/NLQTSBench`](https://huggingface.co/datasets/mrtan/NLQTSBench).
220 natural-language-query / time-series tasks sampled from the same
candidate pool as the NLQTSBench test set, then filtered to be **disjoint
by `id`** from the test split.

Intended use: cold-start training of methodology skills for the
[Sonar-TS](https://github.com/...) framework. **Do not** use this split
for benchmarking — it overlaps the test set's *task templates* even
though no individual task `id` appears in both.

## Files

```
NLQTSBench-train/
├── tasks.json          220 task records (one JSON list)
└── ts_data/
    └── <id>.csv        220 raw time-series CSVs (one per task)
```

## Schema

Each entry in `tasks.json` has these fields:

| Field          | Type           | Description                                                                 |
|----------------|----------------|-----------------------------------------------------------------------------|
| `id`           | str            | Unique task id, e.g. `L1_T1_Global_Aggregation_00014`.                      |
| `level`        | int (1–4)      | Reasoning level (paper Table 2).                                            |
| `level_name`   | str            | Human-readable level name (`Basic Operations`, …).                          |
| `category`     | str            | Higher-level category (`Atomic Retrieval`, `Pattern Recognition`, …).       |
| `subtask`      | str            | One of 10 sub-task labels (see counts below — Composite Trend is absent).   |
| `question`     | str            | Natural-language query, includes the expected answer format.                |
| `answer`       | str            | Ground-truth answer as a string (display form).                             |
| `ground_truth` | varies         | Ground-truth value in its native Python type (number / list / dict).        |
| `eval_metric`  | str            | One of `rel_acc`, `hit`, `iou`, `set_f1`, `report`.                         |
| `channel`      | str / list     | Channel name(s) referenced by the question.                                 |
| `ts_data_path` | str            | Relative path to the matching CSV under `ts_data/`.                         |
| `meta`         | dict           | Generation metadata (template args, source dataset).                        |

Each `ts_data/<id>.csv` is a wide table whose first column is `timestamp`
and remaining columns are numeric channels.

## Sub-task distribution

| Sub-task                | N   |
|-------------------------|-----|
| Sliding Window          | 38  |
| Interval Discovery      | 33  |
| Temporal Localization   | 31  |
| Global Aggregation      | 28  |
| Causal Anomaly          | 18  |
| Subsequence Matching    | 16  |
| Contextual Anomaly      | 14  |
| Insight Synthesis       | 14  |
| Periodicity Detection   | 14  |
| Shape Identification    | 14  |
| **Composite Trend**     | **0** |
| **Total**               | **220** |

**Composite Trend is intentionally absent**: its candidate pool was
fully consumed by the test split with no disjoint tasks left over.

## Disjointness with the test split

Tasks were sampled with a distinct seed and then any `id` that also
appears in [`mrtan/NLQTSBench`](https://huggingface.co/datasets/mrtan/NLQTSBench)
was dropped. The remaining 220 task `id`s do **not** overlap with the
test set.

## Loading

```python
from huggingface_hub import snapshot_download
snapshot_download(repo_id="mrtan/NLQTSBench-train",
                  repo_type="dataset",
                  local_dir="NLQTSBench-train")

import json, pandas as pd
tasks = json.load(open("NLQTSBench-train/tasks.json"))
df    = pd.read_csv(f"NLQTSBench-train/{tasks[0]['ts_data_path']}")
```

For the Sonar-TS framework, just run:

```bash
python -m cold_start.download_train_data
```

which pulls this dataset and builds per-task SQLite + SAX feature tables
locally under `cold_start/train_data/`.

## License

Apache-2.0, matching the test-split licence.
