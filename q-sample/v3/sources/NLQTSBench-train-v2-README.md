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
pretty_name: NLQTSBench-train-v2
---

# NLQTSBench-train-v2

Second training set for [NLQTSBench](https://huggingface.co/datasets/mrtan/NLQTSBench).
It sits next to [`mrtan/NLQTSBench-train`](https://huggingface.co/datasets/mrtan/NLQTSBench-train), which is unchanged.

It holds 690 tasks over all 11 sub-tasks, including Composite Trend.
The skill library of the [Sonar-TS `moso` branch](https://github.com/Atlamtiz/Sonar-TS/tree/moso) was distilled from it.

The tasks use the same question templates as the test set, generated with different and more widely varying parameters.
No task `id` and no question text of this set appears in the test set.
Do **not** use it for benchmarking.

## Files

```
NLQTSBench-train-v2/
├── general/
│   ├── tasks.json        500 tasks, all 11 sub-tasks
│   ├── splits.json       train 300 / valid 198 / excluded 2
│   └── ts_data/<id>.csv  500 CSVs
└── composite_trend/
    ├── tasks.json        190 Composite Trend tasks
    ├── splits.json       train 120 / valid 60 / spare 10
    └── ts_data/<id>.csv  190 CSVs
```

The `train` ids feed the cold-start stream, and the `valid` ids select the skill library.
The two `excluded` tasks have a degenerate interval ground truth and are not scored.

## Schema

`tasks.json` has the same fields as the test set and v1:
`id`, `level`, `level_name`, `category`, `subtask`, `question`, `answer`, `ground_truth`, `eval_metric`, `channel`, `ts_data_path`.
There is no `meta` field.
Each `ts_data/<id>.csv` is a wide table whose first column is `timestamp`, followed by numeric channels.

## Sub-task distribution

| Sub-task | general | composite_trend |
|---|---|---|
| Global Aggregation | 45 | 0 |
| Temporal Localization | 45 | 0 |
| Interval Discovery | 45 | 0 |
| Sliding Window | 45 | 0 |
| Shape Identification | 45 | 0 |
| Periodicity Detection | 45 | 0 |
| Subsequence Matching | 45 | 0 |
| Composite Trend | 50 | 190 |
| Contextual Anomaly | 45 | 0 |
| Causal Anomaly | 45 | 0 |
| Insight Synthesis | 45 | 0 |
| **Total** | **500** | **190** |

## Loading

```python
from huggingface_hub import snapshot_download
snapshot_download(repo_id="mrtan/NLQTSBench-train-v2",
                  repo_type="dataset",
                  local_dir="NLQTSBench-train-v2")

import json, pandas as pd
root = "NLQTSBench-train-v2/composite_trend"
tasks = json.load(open(f"{root}/tasks.json"))
df = pd.read_csv(f"{root}/{tasks[0]['ts_data_path']}")
```

## License

Apache-2.0, matching the test set.
