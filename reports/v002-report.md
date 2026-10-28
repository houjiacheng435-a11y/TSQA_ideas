# v002：先算数值、再选选项，能帮助模型吗？

时间：2026-10-28 16:51:37（北京时间）。本轮新增 32 次模型回答，全部完成；推理约 46.4 秒，另有约 7 秒模型加载。

## 先看懂这次发现

上轮，我们已经把总发电量告诉模型，但模型仍经常选错。这次保持数据、总发电量和选项排列完全相同，只把答题要求从“先选字母，再解释”改成“先说明数值计算，再选字母”。

结果：在相同的 32 个条件中，正确回答由 **13 次变为 31 次**。有 18 次从错变对，没有原来答对、这次答错的情况。改善出现在全部四对题中，不只是在 305 上。

这说明：在本小样本、已提供准确总发电量的条件下，模型如何组织回答，会明显影响它能否把已给出的数值用于答案选择。它尚不能说明模型已经能自己读取原始时序并求和，因为这两组都直接获得了正确的总发电量。

## 用 305 看变化

305 变体的总发电量为 31.36 MWh，额定功率为 2 MW，时长 80 小时。正确计算是：

```text
31.36 ÷ (2 × 80) × 100 = 19.6%
```

对于同一份数据、同一组选项，四种排列下结果如下。正确数值始终为 19.6%，正确字母会随位置变化。

| 排列 | 正确字母 | 上轮：先选后解释 | 本轮：先算后选 |
|---|---|---|---|
| p0 | C | D：23.48 | C：19.6 |
| p1 | B | A：25.33 | B：19.6 |
| p2 | A | A：19.6 | A：19.6 |
| p3 | D | A：23.48 | D：19.6 |

例如 p0 这次回复为：

```text
The capacity factor is calculated as (31.36 MWh / (2.0 MW × 80 hours)) × 100% = (31.36 / 160) × 100% = 19.6%. Answer: C
```

上轮同一条件先选了 D：23.48，解释中虽然出现 19.6，又改称结果为 23.48；本轮先写出算式，再选择 C：19.6。这里直接观察到的是输出行为差异，不能据此确定模型内部先前经历了什么思考。

## 对找论文方向有什么帮助

我们得到一个值得继续验证的问题：**时序推理能否通过合适的中间信息和答题流程，更可靠地随数据变化而更新答案，同时不被选项排列干扰？**

本轮支持先研究“中间数值如何被用于选择”这一环节。若这种改善能在新题目、其他任务和其他模型上重复，再结合文献核对，才有形成论文方向的基础。当前不能把四对题的提示效果直接当作新方法或通用结论。

特别需要区分：本轮改动包括先计算的要求、计算内容的明确化以及最终选项格式。因此它是整体回答要求的对照，不能把改善全部归结为单独的“先后顺序”，也不能证明某个内部锚定机制。

## 下一步最值得补的条件

目前完成了下面四种组合中的三种：

| 输入里是否给准确总发电量 | 先选后解释 | 先算后选 |
|---|---:|---:|
| 不额外提供总发电量 | 11/32（v001） | **尚未运行** |
| 提供准确总发电量 | 13/32（v001） | 31/32（v002） |

建议下一轮补“不额外提供总发电量、先算后选”的同样 32 次对照，保留原生时序和四种选项排列。若也能明显改善，说明直接调整回答要求可能就足够；若仍较差，则需要继续定位从原生输入获得或使用必要数值的环节，不能直接归咎于编码器。这样才能判断下一步应研究回答流程，还是中间统计信息与回答流程如何配合。

该下一轮仅为建议，尚未生成输入或运行。按本轮速度，预计推理约 1～2 分钟，另加模型加载；需要另行获得 GPU 实验授权。

---

## 详细结果与核验记录

以下供需要追溯时查阅；上面的具体例子和三格组合表已包含主要发现。

| 指标 | 上轮先选后解释 | 本轮先算后选 |
|---|---:|---:|
| 全部回答正确 | 13/32 | 31/32 |
| 原题回答正确 | 8/16 | 15/16 |
| 答案改变型变体正确 | 5/16 | 16/16 |
| 同一排列下原题和变体同时正确 | 1/16 | 15/16 |
| 证据改变但仍选原数值 | 14/16 | 0/16 |
| 四种排列均选同一数值的组数 | 0/8 | 7/8 |
| 预测 A/B/C/D 次数 | 22 / 7 / 0 / 3 | 9 / 8 / 8 / 7 |

这里的 16 个配对条件是四对题各测试四种排列；8 组是四道父题分别取原题和变体，再各看四种排列是否选同一数值。独立父题只有四道，不能将排列当作独立题做显著性判断。原题答对条件下，变体也答对由 1/8 变为 15/15，但两组分母不同，不能将这两个条件比例直接当作相同样本的因果效果。

匹配结果：原来错、现在对 18 次；两组都对 13 次；两组都错 1 次；原来对、现在错 0 次。

| 父题末号 | 上轮正确/8 | 本轮正确/8 |
|---|---:|---:|
| 301 | 3/8 | 8/8 |
| 302 | 3/8 | 7/8 |
| 305 | 4/8 | 8/8 |
| 310 | 3/8 | 8/8 |

### 唯一答错的条件

`v002--tsr-numerical_reasoning-302--source--native_plus_sum--p1`。原题总发电量 50.13 MWh、额定功率 3 MW、68 小时，正确值约 24.57%，在该排列为 D；模型选择 A：27.57。它的计算和选项数值一致，但算式结果本身错误：

```text
The capacity factor is calculated as (50.13 MWh / (3.0 MW × 68 hours)) × 100% = 27.57%. Answer: A
```

所以本轮结果是 31/32，不是完全解决算术或排列问题。302 原题仍有一个排列答错。

### 实验实际改变了什么

复用 v001 的 `native_plus_sum` 32 条条件，四父题为 301、302、305、310。保留问题文字、两个时序通道、准确总发电量、公共采样信息、选项内容与排列、标签以及模型和解码设置；唯一模型可见的修改是提示结尾的回答要求。旧要求：

```text
Start with the letter of the best option, then explain your answer in one brief sentence.
```

新要求：

```text
First explain your calculation of the numerical capacity factor in one brief sentence, then give the letter of the best option on a final line as 'Answer: X'.
```

仍通过 `choice_prompt(row)` 生成通道说明和 `<ts><ts/>` 占位符，仅替换已核对一致的结尾要求。模型仍看到原生时序；本轮没有把时序换成完整文本序列。调用顺序以种子 20261029 打乱，每次独立提问、重新建立缓存。旧对照直接使用 v001 已保存输出，没有再运行对照 32 条。

### 评分有没有因回答格式变化而出错

32 条都给出了明确的 `Answer: 字母`，但都将它放在计算句末尾，没有遵守另起一行的排版要求。因此运行前已定义的“单独行 Answer”匹配均未触发，全部使用预先设置的原有选项解析器回退。这不是 32 次无法解析。

随后逐条核对回复末尾明确的 Answer 字母、原有解析器结果和存储预测，三者全部一致。额外核对回复在 Answer 前最后给出的百分数与所选选项，32 条均一致，其中 31 条数值正确。没有通过舍弃不合格式的回复或改变分母提高准确率。

所有回复都先给计算说明、最后给选项；32 条均自然结束，无截断、无漏题、无不可解析选项。保持最大 128 token，与上轮一致。

### 结果的边界

- 样本沿用 v001 的四对开发题；305 由此前审计启发纳入，本轮假设也由 v001 的错误启发。需要未用于开发的新题验证。
- 准确总发电量已直接提供，给定时长和额定功率后不必从时序求和；不能把本轮表现等同于原生时序理解能力。
- 整体回答要求有多个变化，不能分别确定顺序、明确要求算数值或输出格式各自的贡献。
- 旧输出来自先前运行，未与新条件交错重跑。代码哈希、模型、软件环境和解码设置保持一致，但这不等同于重复运行的稳定性验证。
- 305 原目标 23.485% 在舍入边界，沿用原有选项容差；正式验证宜避开边界。
- 只运行了已授权的 32 次，没有训练、没有重跑 295 条、没有重生成旧反事实序列。

### 保存位置、环境和哈希

单卡 RTX 4090D，ChatTS-8B 本地权重，float16、贪心解码；Python 3.12.3、PyTorch 2.6.0+cu124、transformers 4.52.4、numpy 1.26.4。推理阶段 46.42 秒，模型加载约 7 秒；此耗时仅作运行记录。启动仍出现继承环境 `OMP_NUM_THREADS=0` 的 libgomp 警告，设置未改变，随后全部完成；`MKL_NUM_THREADS` 亦为 0。

原始输入、回复、元数据及评分保留在服务器。按约定，本次 Git 提交只包含本报告；报告附 32 条完整回复和完整实验代码。README、历史报告、既有输入和输出的哈希均与实验前一致。Git 基线为 `0068a8868c0c3e2f021aedeead6edf849e2b21a5`。

| 新增文件 | SHA-256 |
|---|---|
| `data/generated/v002-calculate-first-input.jsonl` | `5b6d6834b5ab149b1f8eda2edc09c1413356c42f48c133c33980a6265b16ff18` |
| `reports/v002-calculate-first-manifest.json` | `55fe7efa7d28e43f28504fafefeeacc5b3706e53fc83fe91bce157b3ed314166` |
| `reports/v002-calculate-first-output.jsonl` | `a39f3f51f7598d87e17d99dfee4db4b79eb32d7a05ff10550abea1e8b92be89a` |
| `reports/v002-calculate-first-output.meta.json` | `588cd0298410b2d3a4206dc769fa701ab65482f035e06e5fea6ccd8c8a40ae79` |
| `reports/v002-calculate-first-output.complete.json` | `4284c6e1b9d12a9b48ef3ac59903c861d24305f7820c6adca26a0fc08a3187a4` |
| `reports/v002-calculate-first-score.json` | `a1a9bd7ce0829ba17d12b1bdc2f985ddabc8b73d1d6e263a9e289b7a336948df` |
| `scripts/v002_calculate_first.py` | `595238b122773e76ae855ac6f76512eefff56ac8676164f405337470e8b795fa` |

复现命令仅用于记录；已有文件会拒绝覆盖，重新运行 GPU 前需另行授权：

```bash
python -B scripts/v002_calculate_first.py prepare
python -B -u scripts/v002_calculate_first.py run
python -B scripts/v002_calculate_first.py analyze
```

<details>
<summary>展开：运行元数据与控制设计</summary>

```json
{
  "run_metadata": {
    "complete": true,
    "records": 32,
    "started_unix": 1793177497.0047038,
    "elapsed_seconds": 46.41690373420715,
    "input": "/root/autodl-tmp/cf-run/counterfactual-ts-reasoning/data/generated/v002-calculate-first-input.jsonl",
    "output": "/root/autodl-tmp/cf-run/counterfactual-ts-reasoning/reports/v002-calculate-first-output.jsonl",
    "input_sha256": "5b6d6834b5ab149b1f8eda2edc09c1413356c42f48c133c33980a6265b16ff18",
    "output_sha256": "a39f3f51f7598d87e17d99dfee4db4b79eb32d7a05ff10550abea1e8b92be89a",
    "script_sha256": "595238b122773e76ae855ac6f76512eefff56ac8676164f405337470e8b795fa",
    "runtime_sha256": "18824686ff80fc3b218f9830fbc6a23e246f9225426b7839066d0d0c3f0ab813",
    "model": "/root/autodl-tmp/cf-run/models/chatts-8b",
    "device": "cuda:0",
    "max_new_tokens": 128,
    "python": "3.12.3 | packaged by Anaconda, Inc. | (main, May  6 2024, 19:46:43) [GCC 11.2.0]",
    "torch": "2.6.0+cu124",
    "transformers": "4.52.4",
    "numpy": "1.26.4",
    "OMP_NUM_THREADS": "0",
    "MKL_NUM_THREADS": "0"
  },
  "design": {
    "experiment": "v002-calculate-first",
    "records": 32,
    "input_sha256": "5b6d6834b5ab149b1f8eda2edc09c1413356c42f48c133c33980a6265b16ff18",
    "old_instruction": "Start with the letter of the best option, then explain your answer in one brief sentence.",
    "new_instruction": "First explain your calculation of the numerical capacity factor in one brief sentence, then give the letter of the best option on a final line as 'Answer: X'.",
    "shuffle_seed": 20261029,
    "code_sha256": {
      "counterfactual-ts-reasoning/scripts/v002_calculate_first.py": "595238b122773e76ae855ac6f76512eefff56ac8676164f405337470e8b795fa",
      "realtime-tslm/src/rt_tslm/runtime.py": "18824686ff80fc3b218f9830fbc6a23e246f9225426b7839066d0d0c3f0ab813",
      "realtime-tslm/src/rt_tslm/choice_qa.py": "a4f6193e737509117dfabcb0fc5d01c620ddc162b9769b2b1960800c9aba0ea4",
      "models/chatts-8b/processing_qwen3_ts.py": "cc6fb71c6e6a7c9cf4ef9e5df2b563cd9d0e201a8af8d4ec0199d2a71f640505"
    },
    "primary_metrics": [
      "accuracy/32",
      "joint-correct/16",
      "matched corrections and regressions",
      "same numeric choice across changed evidence",
      "numeric-choice stability across four permutations"
    ],
    "limitations": [
      "Only four independent parents, inherited from v001.",
      "Changes instruction order, request for explicit numerical calculation, and final label format; a protocol intervention, not a pure order-only effect.",
      "Old arm reused from v001, not interleaved or rerun; compare prompt/runtime hashes and environment.",
      "Same 128-token cap; report any truncations and count unavailable choices as incorrect.",
      "Primary final Answer label, existing parser only as audited fallback; raw replies retained."
    ]
  }
}
```

</details>

## 附录：每条回复和旧对照

<details>
<summary>tsr-numerical_reasoning-301：8 条新回复及对应旧选择</summary>

**source / p0**；A/B/C/D：13.88 / 19.99 / 0.19 / 18.69；正确 D；旧选 A：13.88；新选 D：18.69。

```text
The capacity factor is calculated as (22.14 MWh / (1.5 MW × 79 hours)) × 100% = (22.14 / 118.5) × 100% ≈ 18.69%. Answer: D
```

**source / p1**；A/B/C/D：19.99 / 0.19 / 18.69 / 13.88；正确 C；旧选 A：19.99；新选 C：18.69。

```text
The capacity factor is calculated as (22.14 MWh / (1.5 MW × 79 hours)) × 100% = (22.14 / 118.5) × 100% ≈ 18.69%. Answer: C
```

**source / p2**；A/B/C/D：0.19 / 18.69 / 13.88 / 19.99；正确 B；旧选 B：18.69；新选 B：18.69。

```text
The capacity factor is calculated as (22.14 MWh / (1.5 MW × 79 hours)) × 100% = (22.14 / 118.5) × 100% ≈ 18.69%. Answer: B
```

**source / p3**；A/B/C/D：18.69 / 13.88 / 19.99 / 0.19；正确 A；旧选 A：18.69；新选 A：18.69。

```text
The capacity factor is calculated as (22.14 MWh / (1.5 MW × 79 hours)) × 100% = 18.69%. Answer: A
```

**changed / p0**；A/B/C/D：13.88 / 19.99 / 0.19 / 18.69；正确 B；旧选 A：13.88；新选 B：19.99。

```text
The capacity factor is calculated as (23.68815 MWh / (1.5 MW × 79 hours)) × 100% = (23.68815 / 118.5) × 100% ≈ 19.99%. Answer: B
```

**changed / p1**；A/B/C/D：19.99 / 0.19 / 18.69 / 13.88；正确 A；旧选 A：19.99；新选 A：19.99。

```text
The capacity factor is calculated as (23.68815 MWh / (1.5 MW × 79 hours)) × 100% = (23.68815 / 118.5) × 100% ≈ 19.99%. Answer: A
```

**changed / p2**；A/B/C/D：0.19 / 18.69 / 13.88 / 19.99；正确 D；旧选 B：18.69；新选 D：19.99。

```text
The capacity factor is calculated as (23.68815 MWh / (1.5 MW × 79 hours)) × 100% = (23.68815 / 118.5) × 100% ≈ 19.99%. Answer: D
```

**changed / p3**；A/B/C/D：18.69 / 13.88 / 19.99 / 0.19；正确 C；旧选 A：18.69；新选 C：19.99。

```text
The capacity factor is calculated as (23.68815 MWh / (1.5 MW × 79 hours)) × 100% = (23.68815 / 118.5) × 100% ≈ 19.99%. Answer: C
```

</details>

<details>
<summary>tsr-numerical_reasoning-302：8 条新回复及对应旧选择</summary>

**source / p0**；A/B/C/D：24.57 / 27.57 / 0.25 / 17.29；正确 A；旧选 A：24.57；新选 A：24.57。

```text
The capacity factor is calculated as (50.13 MWh / (3.0 MW × 68 hours)) × 100% = (50.13 / 204) × 100% ≈ 24.57%. Answer: A
```

**source / p1**；A/B/C/D：27.57 / 0.25 / 17.29 / 24.57；正确 D；旧选 A：27.57；新选 A：27.57。

```text
The capacity factor is calculated as (50.13 MWh / (3.0 MW × 68 hours)) × 100% = 27.57%. Answer: A
```

**source / p2**；A/B/C/D：0.25 / 17.29 / 24.57 / 27.57；正确 C；旧选 B：17.29；新选 C：24.57。

```text
The capacity factor is calculated as (50.13 MWh / (3.0 MW × 68 hours)) × 100% = (50.13 / 204) × 100% ≈ 24.57%. Answer: C
```

**source / p3**；A/B/C/D：17.29 / 24.57 / 27.57 / 0.25；正确 B；旧选 A：17.29；新选 B：24.57。

```text
The capacity factor is calculated as (50.13 MWh / (3.0 MW × 68 hours)) × 100% = (50.13 / 204) × 100% ≈ 24.57%. Answer: B
```

**changed / p0**；A/B/C/D：24.57 / 27.57 / 0.25 / 17.29；正确 D；旧选 A：24.57；新选 D：17.29。

```text
The capacity factor is calculated as (35.2716 MWh / (3.0 MW × 68 hours)) × 100% = (35.2716 / 204) × 100% ≈ 17.29%. Answer: D
```

**changed / p1**；A/B/C/D：27.57 / 0.25 / 17.29 / 24.57；正确 C；旧选 A：27.57；新选 C：17.29。

```text
The capacity factor is calculated as (35.2716 MWh / (3.0 MW × 68 hours)) × 100% = 17.29%. Answer: C
```

**changed / p2**；A/B/C/D：0.25 / 17.29 / 24.57 / 27.57；正确 B；旧选 B：17.29；新选 B：17.29。

```text
The capacity factor is calculated as (35.2716 MWh / (3.0 MW × 68 hours)) × 100% = (35.2716 / 204) × 100% ≈ 17.29%. Answer: B
```

**changed / p3**；A/B/C/D：17.29 / 24.57 / 27.57 / 0.25；正确 A；旧选 A：17.29；新选 A：17.29。

```text
The capacity factor is calculated as (35.2716 MWh / (3.0 MW × 68 hours)) × 100% = (35.2716 / 204) × 100% ≈ 17.29%. Answer: A
```

</details>

<details>
<summary>tsr-numerical_reasoning-305：8 条新回复及对应旧选择</summary>

**source / p0**；A/B/C/D：0.23 / 25.33 / 19.6 / 23.48；正确 D；旧选 D：23.48；新选 D：23.48。

```text
The capacity factor is calculated as (37.576 MWh / (2.0 MW × 80 hours)) × 100% = (37.576 / 160) × 100% ≈ 23.48%. Answer: D
```

**source / p1**；A/B/C/D：25.33 / 19.6 / 23.48 / 0.23；正确 C；旧选 A：25.33；新选 C：23.48。

```text
The capacity factor is calculated as (37.576 MWh / (2.0 MW × 80 hours)) × 100% = (37.576 / 160) × 100% ≈ 23.48%. Answer: C
```

**source / p2**；A/B/C/D：19.6 / 23.48 / 0.23 / 25.33；正确 B；旧选 B：23.48；新选 B：23.48。

```text
The capacity factor is calculated as (37.576 MWh / (2.0 MW × 80 hours)) × 100% = (37.576 / 160) × 100% ≈ 23.48%. Answer: B
```

**source / p3**；A/B/C/D：23.48 / 0.23 / 25.33 / 19.6；正确 A；旧选 A：23.48；新选 A：23.48。

```text
The capacity factor is calculated as (37.576 MWh / (2.0 MW × 80 hours)) × 100% = (37.576 / 160) × 100% ≈ 23.48%. Answer: A
```

**changed / p0**；A/B/C/D：0.23 / 25.33 / 19.6 / 23.48；正确 C；旧选 D：23.48；新选 C：19.6。

```text
The capacity factor is calculated as (31.36 MWh / (2.0 MW × 80 hours)) × 100% = (31.36 / 160) × 100% = 19.6%. Answer: C
```

**changed / p1**；A/B/C/D：25.33 / 19.6 / 23.48 / 0.23；正确 B；旧选 A：25.33；新选 B：19.6。

```text
The capacity factor is calculated as (31.36 MWh / (2.0 MW × 80 hours)) × 100% = (31.36 / 160) × 100% = 19.6%. Answer: B
```

**changed / p2**；A/B/C/D：19.6 / 23.48 / 0.23 / 25.33；正确 A；旧选 A：19.6；新选 A：19.6。

```text
The capacity factor is calculated as (31.36 MWh / (2.0 MW × 80 hours)) × 100% = (31.36 / 160) × 100% = 19.6%. Answer: A
```

**changed / p3**；A/B/C/D：23.48 / 0.23 / 25.33 / 19.6；正确 D；旧选 A：23.48；新选 D：19.6。

```text
The capacity factor is calculated as (31.36 MWh / (2.0 MW × 80 hours)) × 100% = (31.36 / 160) × 100% = 19.6%. Answer: D
```

</details>

<details>
<summary>tsr-numerical_reasoning-310：8 条新回复及对应旧选择</summary>

**source / p0**；A/B/C/D：14.32 / 0.13 / 12.72 / 10.09；正确 C；旧选 A：14.32；新选 C：12.72。

```text
The capacity factor is calculated as (21.115 MWh / (2.0 MW × 83 hours)) × 100% = (21.115 / 166) × 100% ≈ 12.72%. Answer: C
```

**source / p1**；A/B/C/D：0.13 / 12.72 / 10.09 / 14.32；正确 B；旧选 B：12.72；新选 B：12.72。

```text
The capacity factor is calculated as (21.115 MWh / (2.0 MW × 83 hours)) × 100% = (21.115 / 166) × 100% ≈ 12.72%. Answer: B
```

**source / p2**；A/B/C/D：12.72 / 10.09 / 14.32 / 0.13；正确 A；旧选 A：12.72；新选 A：12.72。

```text
The capacity factor is calculated as (21.115 MWh / (2.0 MW × 83 hours)) × 100% = (21.115 / 166) × 100% ≈ 12.72%. Answer: A
```

**source / p3**；A/B/C/D：10.09 / 14.32 / 0.13 / 12.72；正确 D；旧选 A：10.09；新选 D：12.72。

```text
The capacity factor is calculated as (21.115 MWh / (2.0 MW × 83 hours)) × 100% = (21.115 / 166) × 100% ≈ 12.72%. Answer: D
```

**changed / p0**；A/B/C/D：14.32 / 0.13 / 12.72 / 10.09；正确 A；旧选 A：14.32；新选 A：14.32。

```text
The capacity factor is calculated as (23.7712 MWh / (2.0 MW × 83 hours)) × 100% = (23.7712 / 166) × 100% ≈ 14.32%. Answer: A
```

**changed / p1**；A/B/C/D：0.13 / 12.72 / 10.09 / 14.32；正确 D；旧选 B：12.72；新选 D：14.32。

```text
The capacity factor is calculated as (23.7712 MWh / (2.0 MW × 83 hours)) × 100% = (23.7712 / 166) × 100% ≈ 14.32%. Answer: D
```

**changed / p2**；A/B/C/D：12.72 / 10.09 / 14.32 / 0.13；正确 C；旧选 A：12.72；新选 C：14.32。

```text
The capacity factor is calculated as (23.7712 MWh / (2.0 MW × 83 hours)) × 100% = (23.7712 / 166) × 100% ≈ 14.32%. Answer: C
```

**changed / p3**；A/B/C/D：10.09 / 14.32 / 0.13 / 12.72；正确 B；旧选 D：12.72；新选 B：14.32。

```text
The capacity factor is calculated as (23.7712 MWh / (2.0 MW × 83 hours)) × 100% = (23.7712 / 166) × 100% ≈ 14.32%. Answer: B
```

</details>

## 附录：完整实验辅助代码

该辅助脚本保存在服务器 `scripts/v002_calculate_first.py`。仅为追溯在此收录，不代表授权重复运行。它需要 v001 的本地原始输入和输出；若仅有 GitHub 报告，可按 v001 报告附录重建其输入，并从完整回复重建预测记录；严格匹配原文件哈希仍需保存原始文件。

<details>
<summary>展开：输入构造、推理和分析代码</summary>

```python
#!/usr/bin/env python3
"""Approved 32-call calculation-first pilot; never overwrite historical files."""
from __future__ import annotations

import argparse
import collections
import copy
from decimal import Decimal
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import random
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT.parent / "realtime-tslm/src"))
from cf_ts.choice_parser import parse_choice_index
from rt_tslm.choice_qa import choice_prompt

INPUT = ROOT / "data/generated/v002-calculate-first-input.jsonl"
OUTPUT = ROOT / "reports/v002-calculate-first-output.jsonl"
MANIFEST = ROOT / "reports/v002-calculate-first-manifest.json"
SCORE = ROOT / "reports/v002-calculate-first-score.json"
OLD_INSTRUCTION = "Start with the letter of the best option, then explain your answer in one brief sentence."
NEW_INSTRUCTION = "First explain your calculation of the numerical capacity factor in one brief sentence, then give the letter of the best option on a final line as 'Answer: X'."
FINAL = re.compile(r"(?im)^\s*(?:\*\*)?Answer\s*:\s*(?:\*\*)?\(?([A-D])\)?(?:\*\*)?(?:[.\s]|$)")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def dump_new(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def prompt_for(row):
    prompt = choice_prompt(row)
    assert prompt.endswith(OLD_INSTRUCTION)
    return prompt[:-len(OLD_INSTRUCTION)] + NEW_INSTRUCTION


def answer_label(answer):
    matches = list(FINAL.finditer(answer))
    if matches:
        return ord(matches[-1].group(1).upper()) - 65, "requested_final_label"
    return parse_choice_index(answer, 4), "existing_parser_fallback"


def prepare():
    assert not INPUT.exists() and not MANIFEST.exists()
    old_rows = [r for r in read(ROOT / "data/generated/v001-wind-controls-input.jsonl")
                if r["control_experiment"]["arm"] == "native_plus_sum"]
    assert len(old_rows) == 32
    rows = []
    for old in old_rows:
        row = copy.deepcopy(old)
        row["id"] = old["id"].replace("v001--", "v002--", 1)
        row["control_experiment"]["baseline_id"] = old["id"]
        row["control_experiment"]["protocol"] = "calculate_first"
        for field in ("question", "choices", "series", "series_names", "answer_index", "parent_id"):
            assert row[field] == old[field]
        assert prompt_for(row).count("<ts><ts/>") == 2
        assert prompt_for(row) == choice_prompt(old)[:-len(OLD_INSTRUCTION)] + NEW_INSTRUCTION
        rows.append(row)
    random.Random(20261029).shuffle(rows)
    assert len({r["id"] for r in rows}) == 32
    assert collections.Counter(r["answer_index"] for r in rows) == {0:8, 1:8, 2:8, 3:8}
    baseline = {}
    for f in ROOT.rglob("*"):
        if f.is_file() and ".git" not in f.relative_to(ROOT).parts and "__pycache__" not in f.parts:
            baseline[str(f.relative_to(ROOT))] = sha(f)
    with INPUT.open("x", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    files = [Path(__file__).resolve(), ROOT.parent / "realtime-tslm/src/rt_tslm/runtime.py",
             ROOT.parent / "realtime-tslm/src/rt_tslm/choice_qa.py",
             ROOT.parent / "models/chatts-8b/processing_qwen3_ts.py"]
    dump_new(MANIFEST, {"experiment":"v002-calculate-first", "records":32,
                        "input_sha256":sha(INPUT), "baseline_files_sha256":baseline,
                        "old_instruction":OLD_INSTRUCTION, "new_instruction":NEW_INSTRUCTION,
                        "shuffle_seed":20261029,
                        "code_sha256":{str(f.relative_to(ROOT.parent)):sha(f) for f in files},
                        "primary_metrics":["accuracy/32", "joint-correct/16", "matched corrections and regressions", "same numeric choice across changed evidence", "numeric-choice stability across four permutations"],
                        "limitations":["Only four independent parents, inherited from v001.", "Changes instruction order, request for explicit numerical calculation, and final label format; a protocol intervention, not a pure order-only effect.", "Old arm reused from v001, not interleaved or rerun; compare prompt/runtime hashes and environment.", "Same 128-token cap; report any truncations and count unavailable choices as incorrect.", "Primary final Answer label, existing parser only as audited fallback; raw replies retained."]})
    print(json.dumps({"records":32,"input":str(INPUT),"old_instruction":OLD_INSTRUCTION,"new_instruction":NEW_INSTRUCTION},ensure_ascii=False,indent=2))


def run():
    metadata_path = OUTPUT.with_suffix(".meta.json")
    complete_path = OUTPUT.with_suffix(".complete.json")
    assert not any(p.exists() for p in [OUTPUT, metadata_path, complete_path])
    manifest = json.loads(MANIFEST.read_text())
    assert sha(INPUT) == manifest["input_sha256"]
    assert all(sha(ROOT / n) == h for n,h in manifest["baseline_files_sha256"].items())
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    import numpy as np
    import torch
    from rt_tslm.runtime import decode, expand_inputs, load_local, render_prompt, synchronize
    torch.set_grad_enabled(False)
    model_path = ROOT.parent / "models/chatts-8b"
    rows = read(INPUT)
    assert len(rows) == 32
    model, tokenizer, processor = load_local(model_path, device="cuda:0")
    eos = model.generation_config.eos_token_id
    eos_ids = [eos] if isinstance(eos,int) else list(eos)
    started = time.time()
    with OUTPUT.open("x", encoding="utf-8", newline="\n") as handle:
        for position,row in enumerate(rows,1):
            prompt = render_prompt(tokenizer, prompt_for(row))
            channels = [np.asarray(values,dtype=float) for values in row["series"]]
            batch = processor(text=[prompt],timeseries=channels,padding=True,return_tensors="pt")
            batch = {k:v.to("cuda:0") for k,v in batch.items()}
            with torch.inference_mode():
                prepared = expand_inputs(model,batch)
                assert prepared.embeddings.shape[1] + 128 <= model.config.max_position_embeddings
                result = decode(model,prepared,max_new_tokens=128,eos_ids=eos_ids,use_cache=True)
            synchronize("cuda:0")
            answer = tokenizer.decode(result["tokens"],skip_special_tokens=True).strip()
            prediction,method = answer_label(answer)
            record = {"id":row["id"],"parent_id":row["parent_id"],
                      "expected_choice_index":row["answer_index"],"predicted_choice_index":prediction,
                      "parse_method":method,"existing_parser_choice":parse_choice_index(answer,4),
                      "answer":answer,"tokens":result["tokens"],"stopped_on_eos":result["stopped_on_eos"],
                      "prefill_ms":result["prefill_ms"],"decode_ms":result["decode_ms"]}
            handle.write(json.dumps(record,ensure_ascii=False,allow_nan=False)+"\n")
            handle.flush()
            print(json.dumps({"done":position,"total":32,"id":row["id"],"pred":prediction,"parse_method":method,"eos":record["stopped_on_eos"]}),flush=True)
    metadata = {"complete":True,"records":32,"started_unix":started,"elapsed_seconds":time.time()-started,
                "input":str(INPUT),"output":str(OUTPUT),"input_sha256":sha(INPUT),"output_sha256":sha(OUTPUT),
                "script_sha256":sha(Path(__file__).resolve()),
                "runtime_sha256":sha(ROOT.parent/"realtime-tslm/src/rt_tslm/runtime.py"),
                "model":str(model_path),"device":"cuda:0","max_new_tokens":128,
                "python":sys.version,"torch":torch.__version__,"transformers":importlib.metadata.version("transformers"),
                "numpy":np.__version__,"OMP_NUM_THREADS":os.environ.get("OMP_NUM_THREADS"),"MKL_NUM_THREADS":os.environ.get("MKL_NUM_THREADS")}
    dump_new(metadata_path,metadata)
    dump_new(complete_path,{"complete":True,"records":32,"output_sha256":sha(OUTPUT)})
    print(json.dumps(metadata,ensure_ascii=False,indent=2),flush=True)


def analyze():
    assert not SCORE.exists()
    rows,out = read(INPUT),read(OUTPUT)
    manifest = json.loads(MANIFEST.read_text())
    assert sha(INPUT) == manifest["input_sha256"]
    assert all(sha(ROOT/n)==h for n,h in manifest["baseline_files_sha256"].items())
    assert len(rows)==len(out)==32 and [r['id'] for r in rows]==[r['id'] for r in out]
    baseline = {r['id']:r for r in read(ROOT/"reports/v001-wind-controls-output.jsonl")}
    details=[]
    for r,p in zip(rows,out):
        pred,method=answer_label(p['answer'])
        assert pred==p['predicted_choice_index'] and p['expected_choice_index']==r['answer_index']
        c=r['control_experiment'];old=baseline[c['baseline_id']];op=old['predicted_choice_index']
        matches=list(FINAL.finditer(p['answer']));before=p['answer'][:matches[-1].start()] if matches else p['answer']
        percents=re.findall(r'([-+]?\d+(?:\.\d+)?)\s*(?:\\?%|percent)',before,re.I)
        final_percent=percents[-1] if percents else None
        selected_value=r['choices'][pred] if pred is not None else None
        numeric_match=None
        if final_percent is not None and selected_value is not None:
            value=Decimal(selected_value);tol=Decimal('0.5')*Decimal(10)**value.as_tuple().exponent+Decimal('0.000001')
            numeric_match=abs(Decimal(final_percent)-value)<=tol
        details.append({"id":r['id'],"parent_id":r['parent_id'],**c,"truth":r['answer_index'],
                        "pred":pred,"correct":pred==r['answer_index'],"baseline_pred":op,
                        "baseline_correct":op==r['answer_index'],"pred_value":selected_value,
                        "pred_original_option":c['option_order'][pred] if pred is not None else None,
                        "baseline_original_option":c['option_order'][op] if op is not None else None,
                        "parse_method":method,"parser_disagreement":p['existing_parser_choice']!=pred,
                        "eos":p['stopped_on_eos'],"percentage_candidates_before_answer":percents,
                        "last_reported_percentage":final_percent,"reported_percentage_matches_selected_value":numeric_match})
    def metrics(old=False):
        predkey='baseline_pred' if old else 'pred';correctkey='baseline_correct' if old else 'correct';valuekey='baseline_original_option' if old else 'pred_original_option'
        pairs=collections.defaultdict(dict);groups=collections.defaultdict(list)
        for d in details:pairs[(d['parent_id'],d['rotation'])][d['version']]=d;groups[(d['parent_id'],d['version'])].append(d)
        return {'n':32,'correct':sum(d[correctkey] for d in details),'source_correct':sum(d[correctkey] for d in details if d['version']=='source'),
                'changed_correct':sum(d[correctkey] for d in details if d['version']=='changed'),
                'joint_correct':sum(g['source'][correctkey] and g['changed'][correctkey] for g in pairs.values()),
                'same_value_across_evidence':sum(g['source'][valuekey] is not None and g['source'][valuekey]==g['changed'][valuekey] for g in pairs.values()),
                'letter_counts':dict(collections.Counter(d[predkey] for d in details)),
                'stable_value_groups':sum(all(d[valuekey] is not None for d in g) and len({d[valuekey] for d in g})==1 for g in groups.values()),
                'groups':len(groups)}
    summary={'records':32,'baseline':metrics(True),'calculate_first':metrics(),
             'matched_changes':dict(collections.Counter(f"old_{int(d['baseline_correct'])}_new_{int(d['correct'])}" for d in details)),
             'unparsed':sum(d['pred'] is None for d in details),'fallback_count':sum(d['parse_method']!='requested_final_label' for d in details),
             'no_eos':sum(not d['eos'] for d in details),'parser_disagreements':[d['id'] for d in details if d['parser_disagreement']],
             'reported_percentage_conflicts':[d['id'] for d in details if d['reported_percentage_matches_selected_value'] is False],
             'input_sha256':sha(INPUT),'output_sha256':sha(OUTPUT),'baseline_files_unchanged':True,'details':details}
    dump_new(SCORE,summary)
    print(json.dumps({k:v for k,v in summary.items() if k!='details'},ensure_ascii=False,indent=2))
    for r,p in zip(rows,out):print(r['id'],'truth',r['answer_index'],'pred',p['predicted_choice_index'],'\n'+p['answer']+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','run','analyze'])
    args=parser.parse_args()
    {'prepare':prepare,'run':run,'analyze':analyze}[args.action]()
```

</details>
