# Counterfactual Time-Series Reasoning

这是一个独立于 `realtime-tslm` 的方向1实验小项目。原项目只作为只读的数据和推理依赖；这里不修改它的原始数据、报告或模型代码。

本项目先用两类可以精确复算答案的 TSRBench 题目建立反事实集：

- **最大交通流量**：答案由一个或少数几个关键时间点的 `密度 × 速度` 最大值决定；
- **风电容量因子**：答案由整段功率序列的总和决定。

每道原题会生成两种反事实版本：

1. `answer_preserving`：数据改变，但程序计算出的正确选项不变；
2. `answer_changing`：决定性数据改变，正确选项变为题目中另一个原有选项。

问题文字、选项及其顺序保持不变。这样模型若改变答案，只能归因于它对输入时序的响应，而不是题干或选项变化。

## 目录

```text
counterfactual-ts-reasoning/
├── data/
│   ├── source/       # 从旧项目筛出的原始种子题（运行脚本后生成）
│   └── generated/    # 反事实题（运行脚本后生成）
├── reports/          # 生成、核验和模型评分结果
├── scripts/          # 可直接运行的命令行脚本
├── src/cf_ts/        # 反事实生成与独立核验的核心逻辑
└── tests/            # 不需要GPU的单元测试
```

## 第一步：生成并检查数据（不需要GPU）

建议在 VS Code 中直接打开 `counterfactual-ts-reasoning` 文件夹，而不是只打开
其中某个 `.py` 文件。项目内的 `.vscode/settings.json` 和 `pyrightconfig.json`
已把 `src/` 声明为源码目录，Pylance 才能识别 `from cf_ts.core import ...`。

在本目录运行：

```powershell
python scripts/select_seed_questions.py
python scripts/generate_counterfactuals.py
python scripts/verify_counterfactuals.py
python scripts/render_manual_review.py
python scripts/freeze_input_manifest.py
python -m unittest discover -s tests -v
```

第一条命令从相邻的 `../realtime-tslm/data/prepared/tsrbench-selected.jsonl` 中筛选交通和风电的100道干净题。它不信任原数据集的 `answer_index`，而是依据显式公式重新计算答案。

第二条命令只接受能够满足以下条件的反事实题：

- 修改后的正确值唯一对应一个**原有选项**；
- 交通密度、速度、风电功率均保持非负；
- 风电功率不超过题目中的额定功率；
- 保持题干、选项、序列长度和变量名称不变。

第三条命令以独立的读取流程重新计算每道题，并检查父题与反事实题之间的关系。生成器和核验器不能使用同一结果文件作为答案来源。

第四条命令会生成 `reports/manual-review-20.md`。它以适合屏幕阅读的方式
抽取20道样本：只显示题目、选项、原答案/新答案、变化位置和统计量，不会把
完整长序列展开。建议在 VS Code 的 Markdown 预览中逐题查看；样本默认折叠，
点击摘要行即可展开一题。

第五条命令在人工检查通过后运行一次，生成不能直接覆盖的
`reports/input-manifest-v1.json`，冻结当前100道原题、195道反事实题和295条
完整推理输入的哈希与ID顺序。后续服务器结果应保存该清单的哈希。

## 之后如何接入模型

`scripts/prepare_inference_input.py` 会把种子题和反事实题合并为一个 JSONL 文件，字段格式保留了旧项目的 `id`、`question`、`choices`、`series` 和 `series_names`，可作为 ChatTS 推理输入。模型输出整理为如下最小格式后，可用评分脚本统计：

```json
{"id": "tsr-numerical_reasoning-200", "predicted_choice_index": 3}
```

```powershell
python scripts/score_counterfactual_results.py --predictions path/to/predictions.jsonl
```

评分会同时报告总体选择正确率，以及在父题回答正确时：

- 对 `answer_preserving` 题是否保持原答案；
- 对 `answer_changing` 题是否切换到新的正确选项。

建议先在服务器上跑24条多样化的冒烟集，再运行完整295条。冒烟集不用于报告
最终指标，只检查模型是否成功加载、回复是否能解析出选项、输出文件格式是否正确：

```powershell
python scripts/build_smoke_input.py
python scripts/run_chatts_greedy.py `
  --model /path/to/models/chatts-8b `
  --input data/generated/smoke_input.jsonl `
  --output reports/chatts-greedy-smoke.jsonl
python scripts/score_counterfactual_results.py `
  --predictions reports/chatts-greedy-smoke.jsonl `
  --report reports/chatts-greedy-smoke-score.json
```

确认冒烟结果无误后，将 `--input` 换成
`data/generated/inference_input.jsonl`，并使用新的输出文件名运行完整295条。推理
脚本要求模型目录带有旧项目运行时要求的 `relay-manifest.json`；这能避免服务器在
下载或版本不一致时悄悄使用其他模型。

## 人工检查的角色

不需要人工为每道题写标签。标签由公式和独立核验程序产生。人工应在模型推理前查看开发阶段的一小批样本，并在正式集上随机抽查约10%～20%，主要检查修改是否自然、变量量纲是否合理。

## 与原项目的边界

- 不修改 `../realtime-tslm` 下的任何文件；
- 新数据记录父题ID、原始序列哈希、修改位置和修改前后的目标值；
- 旧项目的 `runtime.py` 之后仍可作为推理后端，但本项目不复制它，也不在没有GPU的本地环境中假装执行推理。
