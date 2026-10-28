# v001：风电证据更新、选项排列与中间统计量控制实验

实验时间：2026-10-28 16:31:59（北京时间）。状态：64/64 完成；推理阶段 92.24 秒，不含约 11 秒的权重加载。

## 本轮发现与研究意义

在四对风电题的探索性实验中，模型选择随选项排列改变，但相同排列下，原题与答案改变型变体大多选择同一数值。额外提供准确总发电量仅使正确数从 11/32 增至 13/32，新增答对的两次均来自先前审计过的 305。未观察到普遍恢复证据更新的效果。

这为后续研究提出可检验的问题：当计算所需信息已经明确给出时，选项排列和回答协议是否影响模型把正确数值转化为正确选择？这里的回答协议指先给选项还是先给计算结果。目标是找到能稳定改善证据更新的方法，并检验它能否跨题型、跨模型推广；本轮不构成通用机制或论文新颖性的证明。

## 研究假设与对应发现

| 检查 | 预期可区分的假设 | 本轮观察 | 后续帮助 |
|---|---|---|---|
| 固定时序、改变选项排列 | 选择跟随稳定数值，或受选项排列影响 | 每组四种排列都选过不同数值；两输入条件各有 8/8 组如此 | 后续评测需要同时衡量对无关排列的稳定性与对有关证据的正确更新 |
| 原题与改变型变体使用同一排列 | 模型能否随着正确答案变化而更新 | 原生 15/16、加总量 14/16 对仍选同一数值 | 需研究提高证据更新、同时避免无关变化扰动的方法 |
| 额外提供准确总发电量 | 从序列得到统计量是否是唯一主要障碍 | 正确数仅增加 2/32，来自同一父题 | 后续先检查计算到选择的下游过程，再决定是否投入时序编码改造 |
| 查看完整回复 | 回复中的计算与最终选择是否一致 | 305 的一条回复给出 19.6%，又声称结果为 23.48% | 可测试先算后选或显式一致性检查，但不能仅凭文字推断内部推理机制 |

## 样本选择与条件

使用已有四对风电题，未重新生成反事实序列。固定纳入已审计的 305；为覆盖原正确选项 A/B/C/D 各一次并使增大/减小各两对，分别取编号最小的 B-增大（310）、C-增大（301）、D-减小（302）。选择没有读取模型预测，但 305 的纳入受已有审计启发，因此不是盲选随机样本。

| 父题末号 | 原正确选项 | 新正确选项 | 原目标 % | 新目标 % | 方向 |
|---|---|---|---:|---:|---|
| 305 | A | C | 23.485000 | 19.600000 | 减小 |
| 310 | B | C | 12.719880 | 14.320000 | 增大 |
| 301 | C | B | 18.686076 | 19.990000 | 增大 |
| 302 | D | B | 24.573529 | 17.290000 | 减小 |

4 对 × 原题/变体 × 两种输入 × 四种选项排列 = 64 次独立贪心生成。独立父题只有 4 道，不能将 64 次或四次排列当成独立样本进行显著性推断。

两组都使用原生 ChatTS 时序输入、相同问题与以下公共提示。`{hours}` 来自序列长度，额定功率来自题干；每点对应一小时。

```text
Sampling information: each power sample represents one hour. The period contains {hours} hours. Rated power: {capacity} MW.
```

加总量组仅额外增加以下一句；这是由每小时功率积分得到的总发电量，单位 MWh，而不是最终容量因子。保留十位小数，经检查不会改变正确选项。

```text
Computed total actual energy output over this period: {total:.10f} MWh.
```

容量因子 = 总发电量 /（额定功率 × 小时数）× 100%。对这类题，总发电量是计算答案所需的充分统计量，即给定它后，不必再逐点读取功率。

选项使用种子 20261028 随机产生每对题的基础排列，再进行四次循环移位，使每个数值恰好各出现在 A/B/C/D 一次。两版本及两输入组共用相同排列；64 次调用顺序另用种子 20261029 打乱。每次回答重新建立缓存，不展示前题回答。每个输入组正确标签 A/B/C/D 各出现 8 次。

两组继续使用旧 `choice_prompt(row)`，结尾要求先给字母，再简短解释。这一点对研究解释顺序很重要；原生组增加了公共采样提示，因此不应与旧 295 条的原始提示直接作等同对比。

## 汇总结果

| 指标 | 原生时序 | 原生时序＋总发电量 |
|---|---:|---:|
| 总体正确 | 11/32（34.4%） | 13/32（40.6%） |
| 原题正确 | 7/16（43.8%） | 8/16（50.0%） |
| 变体正确 | 4/16（25.0%） | 5/16（31.2%） |
| 原题与变体同时正确 | 0/16（0.0%） | 1/16（6.2%） |
| 原题、变体仍选同一数值 | 15/16（93.8%） | 14/16（87.5%） |
| 原题答对条件下，变体也更新正确 | 0/7 | 1/8 |
| 预测 A/B/C/D 次数 | 22 / 9 / 0 / 1 | 22 / 7 / 0 / 3 |

“同时正确”的分母 16 是四父题各四种排列；条件更新率分母是各组原题答对的排列条件数，两组分母不同，不能当作相同人群的干预效应。未输出可解析选项 0 条；非自然结束 0 条；开头选项与解析选项冲突 0 条；开头数值与所选选项数值冲突 0 条。

匹配同一题、版本、排列比较两输入组：11 个条件两组都对，19 个都错，2 个从错变对，0 个从对变错。预测选项共改变 3 次，其中一次是从错误值改为另一个错误值。两次准确性改善均来自 305，因此不能推广为普遍的中间量提示收益。

| 父题 | 原生正确/8 | 加总量正确/8 |
|---|---:|---:|
| 301 | 3/8 | 3/8 |
| 302 | 3/8 | 3/8 |
| 305 | 2/8 | 4/8 |
| 310 | 3/8 | 3/8 |

## 选项排列的影响

固定时序、题干和输入条件后，四种排列中的预测数值在每组都发生变化；两输入条件分别为 8/8 组。模型也不是始终只选同一个字母：没有任何一组在四次排列中四次都选择同一字母。因此准确表述是存在明显的选项排列依赖及 A/B 倾向，不能简化成“永远选 A”或“纯粹只看位置”。四次循环排列没有覆盖全部 24 种顺序，也不能进一步分离字母标签、前后位置、邻接关系等影响。

| 父题 | 版本 | 输入 | p0→p3 预测字母 | p0→p3 预测数值 |
|---|---|---|---|---|
| 301 | 原题 | 原生 | A → A → B → A | 13.88 → 19.99 → 18.69 → 18.69 |
| 301 | 变体 | 原生 | A → A → B → A | 13.88 → 19.99 → 18.69 → 18.69 |
| 302 | 原题 | 原生 | A → A → B → A | 24.57 → 27.57 → 17.29 → 17.29 |
| 302 | 变体 | 原生 | A → A → B → A | 24.57 → 27.57 → 17.29 → 17.29 |
| 305 | 原题 | 原生 | B → A → B → A | 25.33 → 25.33 → 23.48 → 23.48 |
| 305 | 变体 | 原生 | D → A → B → A | 23.48 → 25.33 → 23.48 → 23.48 |
| 310 | 原题 | 原生 | A → B → A → A | 14.32 → 12.72 → 12.72 → 10.09 |
| 310 | 变体 | 原生 | A → B → A → A | 14.32 → 12.72 → 12.72 → 10.09 |
| 301 | 原题 | 加总量 | A → A → B → A | 13.88 → 19.99 → 18.69 → 18.69 |
| 301 | 变体 | 加总量 | A → A → B → A | 13.88 → 19.99 → 18.69 → 18.69 |
| 302 | 原题 | 加总量 | A → A → B → A | 24.57 → 27.57 → 17.29 → 17.29 |
| 302 | 变体 | 加总量 | A → A → B → A | 24.57 → 27.57 → 17.29 → 17.29 |
| 305 | 原题 | 加总量 | D → A → B → A | 23.48 → 25.33 → 23.48 → 23.48 |
| 305 | 变体 | 加总量 | D → A → A → A | 23.48 → 25.33 → 19.6 → 23.48 |
| 310 | 原题 | 加总量 | A → B → A → A | 14.32 → 12.72 → 12.72 → 10.09 |
| 310 | 变体 | 加总量 | A → B → A → D | 14.32 → 12.72 → 12.72 → 12.72 |

## 305 的计算与选择不一致

此条件已经给出 31.36 MWh、2 MW、80 小时，正确值是 19.6%，对应 C；模型开头选择 D（23.48%），随后回复：

```text
D. 23.48

The capacity factor is calculated as (31.36 MWh / (2.0 MW × 80 hours)) × 100% = (31.36 / 160) × 100% = 19.6%. However, based on the given total actual energy output of 31.36 MWh, the correct calculation is (31.36 / (2.0 × 80)) × 100% = 23.48%.
```

同一变体在 p2 排列中，19.6 位于 A 时，模型选对并给出一致计算；在 p1 排列中，19.6 位于 B 时，却写成 31.36 / (2 × 80) × 100 = 25.33%。这些记录表明，提供完整中间量并不足以保证计算与选择一致。

由于提示要求先选字母、再解释，不能把后生成的正确算式当作模型选答案前已经完成计算的证据，也不能断言发生了某个内部“纠正后被压制”过程。可研究的是可观察的计算—选择不一致，以及改变回答协议能否稳定改善这种不一致。

## 可以支持的判断与限制

- 在这四对题和当前提示下，选择受选项排列影响；时序证据改变时，大多数匹配条件仍选择同一数值。
- 仅补充准确总发电量没有普遍恢复正确更新，不能将问题全部归结为长序列求和。
- 尚不能定位到时序编码器、下游算术或回答承诺顺序中的某一个原因。两组都仍有原生时序输入。
- 四对题是开发阶段探索样本，变化幅度不匹配，包含已审计的 305；没有跨模型、跨题型验证，没有统计显著性结论。
- 305 原目标 23.485% 在舍入边界，沿用原有“半个末位小数加 1e-6”容差；后续正式集应明确舍入规则并避开边界。
- 本轮是可观测行为实验，输出文字不等同于模型内部推理轨迹。

## 对论文方向的帮助及下一步候选

本轮将研究问题推进为：时序推理评测需要同时检验“无关选项变化下保持稳定”和“决定答案的证据变化下正确更新”；还可检验中间数值与最终选择的一致性。若进一步找到能稳定改善这种双重要求的方法，才有形成方法论文的基础。当前发现也可能只是某种提示或模型的局部现象，需文献核对和额外验证。

建议下一轮优先测试“先算后选”回答协议：保留相同八份时序与总量、相同选项排列，仅改变输出顺序，对照本轮加总量组。若采用全部四种排列，需要新增 32 次；可明确检验回答协议能否改善一致性，但“先算后选”的计算要求与输出顺序若同时改变，需将其称为整体协议干预，不能单独归因为顺序。另一个候选是去掉选项的纯文字算术控制，用于检查明确数值下的基本运算。

以上下一轮均未执行，需另行说明样本、耗时并获得同意。本轮没有运行文本完整序列对照、训练、交通重构或完整 295 条推理。

## 运行、文件与完整性记录

模型：ChatTS-8B，本地 revision `7216a84034063c2d394901fe45d20a1e8d773a1f`；RTX 4090D，单卡逐题，float16，贪心生成，最多 128 token。Python 3.12.3；PyTorch 2.6.0+cu124；transformers 4.52.4；numpy 1.26.4。没有重新下载权重。

启动时 libgomp 提示继承的 `OMP_NUM_THREADS=0` 无效；模型随后成功加载并完成全部 64 条。环境同时有 `MKL_NUM_THREADS=0`。本轮未修改这些环境设置，耗时仅作本机记录，不作性能比较。

新增原始文件保留在服务器，不作为本次 Git 提交的独立文件；此报告附完整回复和实验辅助代码，供追溯与重建。原有 40 个已跟踪文件的 SHA-256 均与实验前一致，README 没有修改，既有数据和结果没有覆盖。仓库基线提交为 `cac7412af2eb25864de5931b1a28b833624fd937`。

| 新增文件 | SHA-256 |
|---|---|
| `data/generated/v001-wind-controls-input.jsonl` | `a9074bb2e930b171e5cb5ec68d4f5479ddc44d57a528cebd64bf7f14b16d67f1` |
| `reports/v001-wind-controls-manifest.json` | `af0c4ad00cb8b8df1853a687cbcd9e41f701e90a2e4b58c9e42428399b77db21` |
| `reports/v001-wind-controls-output.jsonl` | `d1cd03ac574452b07b5d9a6f7effd7ddf888bf9e79cef0a1ce4444af61df0b3d` |
| `reports/v001-wind-controls-output.meta.json` | `6a97d9162c242261cefbd82a14a613359ba1bcf742836e78292ad4e6d63e316c` |
| `reports/v001-wind-controls-output.complete.json` | `93f237e7e233d122a40ccdb3b253bc8ed92d8c0fcd23fb8b423ee1586e7458b6` |
| `reports/v001-wind-controls-score.json` | `21f36b21f5ca86f44442689bd72361e358ee5241f2378033137d61063f576476` |
| `scripts/v001_wind_controls.py` | `990a354d8838f04fd2e70fb1d0ec471336e4b7211369a51948401af1f682a911` |

复现命令（仅为记录；重新执行 GPU 命令前需获得授权；已有输出同名文件时脚本会拒绝覆盖）：

```bash
python -B scripts/v001_wind_controls.py prepare
python -B -u scripts/run_chatts_greedy.py --model /root/autodl-tmp/cf-run/models/chatts-8b --input data/generated/v001-wind-controls-input.jsonl --output reports/v001-wind-controls-output.jsonl --max-new-tokens 128
python -B scripts/v001_wind_controls.py analyze
```

<details>
<summary>展开：样本、排列及代码哈希清单</summary>

```json
{
  "experiment": "v001-wind-controls",
  "seed": 20261028,
  "records": 64,
  "selection_rule": "Include 305; original labels A/B/C/D once each; earliest B-up=310, C-up=301, D-down=302; two up/two down. No model predictions used for selection. 305 was motivated by the prior audit, so this is an exploratory, not blind, sample.",
  "selection": [
    {
      "parent_id": "tsr-numerical_reasoning-305",
      "source_choice_index": 0,
      "variant_choice_index": 2,
      "source_target": "23.48500",
      "variant_target": "19.600000000000001940062500",
      "direction": "down",
      "base_option_order": [
        1,
        3,
        2,
        0
      ]
    },
    {
      "parent_id": "tsr-numerical_reasoning-310",
      "source_choice_index": 1,
      "variant_choice_index": 2,
      "source_target": "12.71987951807228915662650602",
      "variant_target": "14.31999999999999700457831325",
      "direction": "up",
      "base_option_order": [
        2,
        3,
        1,
        0
      ]
    },
    {
      "parent_id": "tsr-numerical_reasoning-301",
      "source_choice_index": 2,
      "variant_choice_index": 1,
      "source_target": "18.68607594936708860759493671",
      "variant_target": "19.98999999999999607291139241",
      "direction": "up",
      "base_option_order": [
        3,
        1,
        0,
        2
      ]
    },
    {
      "parent_id": "tsr-numerical_reasoning-302",
      "source_choice_index": 3,
      "variant_choice_index": 1,
      "source_target": "24.57352941176470588235294118",
      "variant_target": "17.29000000000000032058823529",
      "direction": "down",
      "base_option_order": [
        3,
        0,
        2,
        1
      ]
    }
  ],
  "input_sha256": "a9074bb2e930b171e5cb5ec68d4f5479ddc44d57a528cebd64bf7f14b16d67f1",
  "code_sha256": {
    "counterfactual-ts-reasoning/scripts/v001_wind_controls.py": "990a354d8838f04fd2e70fb1d0ec471336e4b7211369a51948401af1f682a911",
    "counterfactual-ts-reasoning/scripts/run_chatts_greedy.py": "9752238aab2e6a21f5c59032f202785bcb9b9a5b3e809efc3e9ef424bdab9abb",
    "realtime-tslm/src/rt_tslm/runtime.py": "18824686ff80fc3b218f9830fbc6a23e246f9225426b7839066d0d0c3f0ab813",
    "realtime-tslm/src/rt_tslm/choice_qa.py": "a4f6193e737509117dfabcb0fc5d01c620ddc162b9769b2b1960800c9aba0ea4",
    "models/chatts-8b/processing_qwen3_ts.py": "cc6fb71c6e6a7c9cf4ef9e5df2b563cd9d0e201a8af8d4ec0199d2a71f640505",
    "models/chatts-8b/relay-manifest.json": "bc752f4c2317b033577d09c9108e638ab9efc13b67c28b3089b2d850fc004f77"
  },
  "design": "4 pairs x 2 versions x 2 arms x 4 balanced rotations; identical permutations for both versions and both arms; independently shuffled call order; no preserving variants; no final-answer hints.",
  "shared_text_template": "Sampling information: each power sample represents one hour. The period contains {hours} hours. Rated power: {capacity} MW.",
  "sum_text_template": "Computed total actual energy output over this period: {total:.10f} MWh.",
  "primary_metrics": [
    "source/changed accuracy",
    "joint-correct parent/changed pairs",
    "correct update conditional on correct parent",
    "letter and numeric-choice consistency over rotations"
  ],
  "limitations": [
    "Only four independent parent questions; rotations are repeated conditions, not independent samples.",
    "Sum arm adds a sufficient statistic and more explicit text; success does not isolate encoder internals.",
    "Native arm adds shared sampling metadata, so it is not an exact rerun of historical prompts.",
    "305 target 23.485 is on a rounding boundary; existing half-last-digit plus 1e-6 tolerance retained."
  ]
}
```
</details>

## 附录：64 条回复和逐条选择

下表 p0–p3 对应上方固定排列；选项池使用原始选项编号进行排列。每个折叠块保存原始回复全文。所有回复均自然结束，最长 122 token。

<details>
<summary>tsr-numerical_reasoning-301 / native：8 条原始回复</summary>

**source / p0**；选项 A/B/C/D：13.88 / 19.99 / 0.19 / 18.69；正确 D；预测 A。

```text
A. 13.88

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (1.5 MW) multiplied by the number of hours (79), then multiplying by 100 to get a percentage. The result is approximately 13.88%.
```

**source / p1**；选项 A/B/C/D：19.99 / 0.19 / 18.69 / 13.88；正确 C；预测 A。

```text
A. 19.99

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (1.5 MW) multiplied by the number of hours (79), then multiplying by 100 to get a percentage. The result is approximately 19.99%.
```

**source / p2**；选项 A/B/C/D：0.19 / 18.69 / 13.88 / 19.99；正确 B；预测 B。

```text
B. 18.69

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (1.5 MW) multiplied by the number of hours (79), then multiplying by 100 to get a percentage. Based on the provided data, this calculation results in approximately 18.69%.
```

**source / p3**；选项 A/B/C/D：18.69 / 13.88 / 19.99 / 0.19；正确 A；预测 A。

```text
A. 18.69

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (1.5 MW) multiplied by the number of hours (79), then multiplying by 100 to get a percentage. The result is approximately 18.69%.
```

**changed / p0**；选项 A/B/C/D：13.88 / 19.99 / 0.19 / 18.69；正确 B；预测 A。

```text
A. 13.88

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (1.5 MW) multiplied by the number of hours (79), then multiplying by 100 to get a percentage. The result is approximately 13.88%.
```

**changed / p1**；选项 A/B/C/D：19.99 / 0.19 / 18.69 / 13.88；正确 A；预测 A。

```text
A. 19.99

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (1.5 MW) multiplied by the number of hours (79), then multiplying by 100 to get a percentage. The result is approximately 19.99%.
```

**changed / p2**；选项 A/B/C/D：0.19 / 18.69 / 13.88 / 19.99；正确 D；预测 B。

```text
B. 18.69

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (1.5 MW) multiplied by the number of hours (79), then multiplying by 100 to get a percentage. Based on the provided data, this calculation results in approximately 18.69%.
```

**changed / p3**；选项 A/B/C/D：18.69 / 13.88 / 19.99 / 0.19；正确 C；预测 A。

```text
A. 18.69

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (1.5 MW) multiplied by the number of hours (79), then multiplying by 100 to get a percentage. The result is approximately 18.69%.
```

</details>

<details>
<summary>tsr-numerical_reasoning-302 / native：8 条原始回复</summary>

**source / p0**；选项 A/B/C/D：24.57 / 27.57 / 0.25 / 17.29；正确 A；预测 A。

```text
A. 24.57

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (3.0 MW) multiplied by the number of hours (68), then multiplying by 100 to get a percentage. The result is approximately 24.57%.
```

**source / p1**；选项 A/B/C/D：27.57 / 0.25 / 17.29 / 24.57；正确 D；预测 A。

```text
A. 27.57

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (3.0 MW) multiplied by the number of hours (68), then multiplying by 100 to get a percentage. The result is approximately 27.57%.
```

**source / p2**；选项 A/B/C/D：0.25 / 17.29 / 24.57 / 27.57；正确 C；预测 B。

```text
B. 17.29

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (3.0 MW) multiplied by the number of hours (68), then multiplying by 100 to get a percentage. Based on the provided data, this calculation results in approximately 17.29%.
```

**source / p3**；选项 A/B/C/D：17.29 / 24.57 / 27.57 / 0.25；正确 B；预测 A。

```text
A. 17.29

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (3.0 MW) multiplied by the number of hours (68), then multiplying by 100 to get a percentage. The result is approximately 17.29%.
```

**changed / p0**；选项 A/B/C/D：24.57 / 27.57 / 0.25 / 17.29；正确 D；预测 A。

```text
A. 24.57

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (3.0 MW) multiplied by the number of hours (68), then multiplying by 100 to get a percentage. The result is approximately 24.57%.
```

**changed / p1**；选项 A/B/C/D：27.57 / 0.25 / 17.29 / 24.57；正确 C；预测 A。

```text
A. 27.57

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (3.0 MW) multiplied by the number of hours (68), then multiplying by 100 to get a percentage. The result is approximately 27.57%.
```

**changed / p2**；选项 A/B/C/D：0.25 / 17.29 / 24.57 / 27.57；正确 B；预测 B。

```text
B. 17.29

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (3.0 MW) multiplied by the number of hours (68), then multiplying by 100 to get a percentage. Based on the provided data, the resulting capacity factor is approximately 17.29%.
```

**changed / p3**；选项 A/B/C/D：17.29 / 24.57 / 27.57 / 0.25；正确 A；预测 A。

```text
A. 17.29

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (3.0 MW) multiplied by the number of hours (68), then multiplying by 100 to get a percentage. The result is approximately 17.29%.
```

</details>

<details>
<summary>tsr-numerical_reasoning-305 / native：8 条原始回复</summary>

**source / p0**；选项 A/B/C/D：0.23 / 25.33 / 19.6 / 23.48；正确 D；预测 B。

```text
B. 25.33

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (2.0 MW) multiplied by the number of hours (80), then multiplying by 100 to get a percentage. The result is approximately 25.33%.
```

**source / p1**；选项 A/B/C/D：25.33 / 19.6 / 23.48 / 0.23；正确 C；预测 A。

```text
A. 25.33

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (2.0 MW) multiplied by the number of hours (80), then multiplying by 100 to get a percentage. The result is approximately 25.33%.
```

**source / p2**；选项 A/B/C/D：19.6 / 23.48 / 0.23 / 25.33；正确 B；预测 B。

```text
B. 23.48

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (2.0 MW) multiplied by the number of hours (80), then multiplying by 100 to get a percentage. The result is approximately 23.48%.
```

**source / p3**；选项 A/B/C/D：23.48 / 0.23 / 25.33 / 19.6；正确 A；预测 A。

```text
A. 23.48

The capacity factor is calculated as (Total Actual Energy Output / (Rated Power × Hours)) × 100%. From the data, the total actual energy output is approximately 3.796 MW·h, the rated power is 2.0 MW, and the total hours are 80. Plugging in the values: (3.796 / (2.0 × 80)) × 100% ≈ 23.48%.
```

**changed / p0**；选项 A/B/C/D：0.23 / 25.33 / 19.6 / 23.48；正确 C；预测 D。

```text
D. 23.48

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (2.0 MW) multiplied by the number of hours (80), then multiplying by 100 to get a percentage. The result is approximately 23.48%.
```

**changed / p1**；选项 A/B/C/D：25.33 / 19.6 / 23.48 / 0.23；正确 B；预测 A。

```text
A. 25.33

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (2.0 MW) multiplied by the number of hours (80), then multiplying by 100 to get a percentage. The result is approximately 25.33%.
```

**changed / p2**；选项 A/B/C/D：19.6 / 23.48 / 0.23 / 25.33；正确 A；预测 B。

```text
B. 23.48

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (2.0 MW) multiplied by the number of hours (80), then multiplying by 100 to get a percentage. The result is approximately 23.48%.
```

**changed / p3**；选项 A/B/C/D：23.48 / 0.23 / 25.33 / 19.6；正确 D；预测 A。

```text
A. 23.48

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (2.0 MW) multiplied by the number of hours (80), then multiplying by 100 to get a percentage. The result is approximately 23.48%.
```

</details>

<details>
<summary>tsr-numerical_reasoning-310 / native：8 条原始回复</summary>

**source / p0**；选项 A/B/C/D：14.32 / 0.13 / 12.72 / 10.09；正确 C；预测 A。

```text
A. 14.32

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (2.0 MW) multiplied by the number of hours (83), then multiplying by 100 to get a percentage. The result is approximately 14.32%.
```

**source / p1**；选项 A/B/C/D：0.13 / 12.72 / 10.09 / 14.32；正确 B；预测 B。

```text
B. 12.72

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (2.0 MW) multiplied by the number of hours (83), then multiplying by 100 to get a percentage. Based on the provided data, this calculation results in approximately 12.72%.
```

**source / p2**；选项 A/B/C/D：12.72 / 10.09 / 14.32 / 0.13；正确 A；预测 A。

```text
A. 12.72

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (2.0 MW) multiplied by the number of hours (83), then multiplying by 100 to get a percentage. The result is approximately 12.72%.
```

**source / p3**；选项 A/B/C/D：10.09 / 14.32 / 0.13 / 12.72；正确 D；预测 A。

```text
A. 10.09

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (2.0 MW) multiplied by the number of hours (83), then multiplying by 100 to get a percentage. The result is approximately 10.09%.
```

**changed / p0**；选项 A/B/C/D：14.32 / 0.13 / 12.72 / 10.09；正确 A；预测 A。

```text
A. 14.32

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (2.0 MW) multiplied by the number of hours (83), then multiplying by 100 to get a percentage. The result is approximately 14.32%.
```

**changed / p1**；选项 A/B/C/D：0.13 / 12.72 / 10.09 / 14.32；正确 D；预测 B。

```text
B. 12.72

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (2.0 MW) multiplied by the number of hours (83), then multiplying by 100 to get a percentage. Based on the provided data, this calculation results in approximately 12.72%.
```

**changed / p2**；选项 A/B/C/D：12.72 / 10.09 / 14.32 / 0.13；正确 C；预测 A。

```text
A. 12.72

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (2.0 MW) multiplied by the number of hours (83), then multiplying by 100 to get a percentage. The result is approximately 12.72%.
```

**changed / p3**；选项 A/B/C/D：10.09 / 14.32 / 0.13 / 12.72；正确 B；预测 A。

```text
A. 10.09

The capacity factor is calculated by dividing the total actual energy output (sum of power output values) by the rated power (2.0 MW) multiplied by the number of hours (83), then multiplying by 100 to get a percentage. The result is approximately 10.09%.
```

</details>

<details>
<summary>tsr-numerical_reasoning-301 / native_plus_sum：8 条原始回复</summary>

**source / p0**；选项 A/B/C/D：13.88 / 19.99 / 0.19 / 18.69；正确 D；预测 A。

```text
A. 13.88

The capacity factor is calculated as (22.14 MWh / (1.5 MW × 79 hours)) × 100% = 13.88%.
```

**source / p1**；选项 A/B/C/D：19.99 / 0.19 / 18.69 / 13.88；正确 C；预测 A。

```text
A. 19.99

The capacity factor is calculated as (22.14 MWh / (1.5 MW × 79 hours)) × 100% = 19.99%.
```

**source / p2**；选项 A/B/C/D：0.19 / 18.69 / 13.88 / 19.99；正确 B；预测 B。

```text
B. 18.69

The capacity factor is calculated as (22.14 MWh / (1.5 MW × 79 hours)) × 100% = 18.69%.
```

**source / p3**；选项 A/B/C/D：18.69 / 13.88 / 19.99 / 0.19；正确 A；预测 A。

```text
A. 18.69

The capacity factor is calculated as (22.14 MWh / (1.5 MW × 79 hours)) × 100% = 18.69%.
```

**changed / p0**；选项 A/B/C/D：13.88 / 19.99 / 0.19 / 18.69；正确 B；预测 A。

```text
A. 13.88

The capacity factor is calculated as (23.68815 MWh / (1.5 MW × 79 hours)) × 100% = 13.88%.
```

**changed / p1**；选项 A/B/C/D：19.99 / 0.19 / 18.69 / 13.88；正确 A；预测 A。

```text
A. 19.99

The capacity factor is calculated as (23.68815 MWh / (1.5 MW × 79 hours)) × 100% ≈ 19.99%.
```

**changed / p2**；选项 A/B/C/D：0.19 / 18.69 / 13.88 / 19.99；正确 D；预测 B。

```text
B. 18.69

The capacity factor is calculated as (23.68815 MWh / (1.5 MW × 79 hours)) × 100% = 18.69%.
```

**changed / p3**；选项 A/B/C/D：18.69 / 13.88 / 19.99 / 0.19；正确 C；预测 A。

```text
A. 18.69

The capacity factor is calculated as (23.68815 MWh / (1.5 MW × 79 hours)) × 100% = 18.69%.
```

</details>

<details>
<summary>tsr-numerical_reasoning-302 / native_plus_sum：8 条原始回复</summary>

**source / p0**；选项 A/B/C/D：24.57 / 27.57 / 0.25 / 17.29；正确 A；预测 A。

```text
A. 24.57

The capacity factor is calculated as (50.13 MWh / (3.0 MW × 68 hours)) × 100% = 24.57%.
```

**source / p1**；选项 A/B/C/D：27.57 / 0.25 / 17.29 / 24.57；正确 D；预测 A。

```text
A. 27.57

The capacity factor is calculated as (50.13 MWh / (3.0 MW × 68 hours)) × 100% = 27.57%.
```

**source / p2**；选项 A/B/C/D：0.25 / 17.29 / 24.57 / 27.57；正确 C；预测 B。

```text
B. 17.29

The capacity factor is calculated as (50.13 MWh / (3.0 MW × 68 hours)) × 100% = 17.29%.
```

**source / p3**；选项 A/B/C/D：17.29 / 24.57 / 27.57 / 0.25；正确 B；预测 A。

```text
A. 17.29

The capacity factor is calculated as (50.13 MWh / (3.0 MW × 68 hours)) × 100% = 17.29%.
```

**changed / p0**；选项 A/B/C/D：24.57 / 27.57 / 0.25 / 17.29；正确 D；预测 A。

```text
A. 24.57

The capacity factor is calculated as (35.27 MWh / (3.0 MW × 68 hours)) × 100% = 24.57%.
```

**changed / p1**；选项 A/B/C/D：27.57 / 0.25 / 17.29 / 24.57；正确 C；预测 A。

```text
A. 27.57

The capacity factor is calculated as (35.2716 MWh / (3.0 MW × 68 hours)) × 100% = 27.57%.
```

**changed / p2**；选项 A/B/C/D：0.25 / 17.29 / 24.57 / 27.57；正确 B；预测 B。

```text
B. 17.29

The capacity factor is calculated as (35.27 MWh / (3.0 MW × 68 hours)) × 100% = 17.29%.
```

**changed / p3**；选项 A/B/C/D：17.29 / 24.57 / 27.57 / 0.25；正确 A；预测 A。

```text
A. 17.29

The capacity factor is calculated as (35.2716 MWh / (3.0 MW × 68 hours)) × 100% = 17.29%.
```

</details>

<details>
<summary>tsr-numerical_reasoning-305 / native_plus_sum：8 条原始回复</summary>

**source / p0**；选项 A/B/C/D：0.23 / 25.33 / 19.6 / 23.48；正确 D；预测 D。

```text
D. 23.48

The capacity factor is calculated as (37.576 MWh / (2.0 MW × 80 hours)) × 100% = 23.48%.
```

**source / p1**；选项 A/B/C/D：25.33 / 19.6 / 23.48 / 0.23；正确 C；预测 A。

```text
A. 25.33

The capacity factor is calculated as (37.576 MWh / (2.0 MW × 80 hours)) × 100% = 25.33%.
```

**source / p2**；选项 A/B/C/D：19.6 / 23.48 / 0.23 / 25.33；正确 B；预测 B。

```text
B. 23.48

The capacity factor is calculated as (37.576 MWh / (2.0 MW × 80 hours)) × 100% = 23.48%.
```

**source / p3**；选项 A/B/C/D：23.48 / 0.23 / 25.33 / 19.6；正确 A；预测 A。

```text
A. 23.48

The capacity factor is calculated as (37.576 MWh / (2.0 MW × 80 hours)) × 100% = 23.48%.
```

**changed / p0**；选项 A/B/C/D：0.23 / 25.33 / 19.6 / 23.48；正确 C；预测 D。

```text
D. 23.48

The capacity factor is calculated as (31.36 MWh / (2.0 MW × 80 hours)) × 100% = (31.36 / 160) × 100% = 19.6%. However, based on the given total actual energy output of 31.36 MWh, the correct calculation is (31.36 / (2.0 × 80)) × 100% = 23.48%.
```

**changed / p1**；选项 A/B/C/D：25.33 / 19.6 / 23.48 / 0.23；正确 B；预测 A。

```text
A. 25.33

The capacity factor is calculated as (31.36 MWh / (2.0 MW × 80 hours)) × 100% = 25.33%.
```

**changed / p2**；选项 A/B/C/D：19.6 / 23.48 / 0.23 / 25.33；正确 A；预测 A。

```text
A. 19.6

The capacity factor is calculated as (31.36 MWh / (2.0 MW × 80 hours)) × 100% = (31.36 / 160) × 100% = 19.6%.
```

**changed / p3**；选项 A/B/C/D：23.48 / 0.23 / 25.33 / 19.6；正确 D；预测 A。

```text
A. 23.48

The capacity factor is calculated as (31.36 MWh / (2.0 MW × 80 hours)) × 100% = 23.48%.
```

</details>

<details>
<summary>tsr-numerical_reasoning-310 / native_plus_sum：8 条原始回复</summary>

**source / p0**；选项 A/B/C/D：14.32 / 0.13 / 12.72 / 10.09；正确 C；预测 A。

```text
A. 14.32

The capacity factor is calculated as (21.115 MWh / (2.0 MW × 83 hours)) × 100% = 14.32%.
```

**source / p1**；选项 A/B/C/D：0.13 / 12.72 / 10.09 / 14.32；正确 B；预测 B。

```text
B. 12.72

The capacity factor is calculated as (21.115 MWh / (2.0 MW × 83 hours)) × 100% = 12.72%.
```

**source / p2**；选项 A/B/C/D：12.72 / 10.09 / 14.32 / 0.13；正确 A；预测 A。

```text
A. 12.72

The capacity factor is calculated as (21.115 MWh / (2.0 MW × 83 hours)) × 100% = 12.72%.
```

**source / p3**；选项 A/B/C/D：10.09 / 14.32 / 0.13 / 12.72；正确 D；预测 A。

```text
A. 10.09

The capacity factor is calculated as (21.115 MWh / (2.0 MW × 83 hours)) × 100% = 10.09%.
```

**changed / p0**；选项 A/B/C/D：14.32 / 0.13 / 12.72 / 10.09；正确 A；预测 A。

```text
A. 14.32

The capacity factor is calculated as (23.77 MWh / (2.0 MW × 83 hours)) × 100% = 14.32%.
```

**changed / p1**；选项 A/B/C/D：0.13 / 12.72 / 10.09 / 14.32；正确 D；预测 B。

```text
B. 12.72

The capacity factor is calculated as (23.77 MWh / (2.0 MW × 83 hours)) × 100% = 12.72%.
```

**changed / p2**；选项 A/B/C/D：12.72 / 10.09 / 14.32 / 0.13；正确 C；预测 A。

```text
A. 12.72

The capacity factor is calculated as (23.77 MWh / (2.0 MW × 83 hours)) × 100% = 12.72%.
```

**changed / p3**；选项 A/B/C/D：10.09 / 14.32 / 0.13 / 12.72；正确 B；预测 D。

```text
D. 12.72

The capacity factor is calculated as (23.77 MWh / (2.0 MW × 83 hours)) × 100% = 12.72%.
```

</details>

## 附录：实验辅助代码

按用户要求，本次仅提交报告。若需在独立副本中重建输入与评分，可将以下代码保存为 `scripts/v001_wind_controls.py`，配合仓库已有推理入口使用。不要在当前已存在同名输出的目录重复运行。

<details>
<summary>展开：完整辅助脚本</summary>

```python
#!/usr/bin/env python3
"""Build the approved 64-condition wind pilot and audit its saved predictions.

This helper does not load a model. GPU inference uses run_chatts_greedy.py.
All outputs are new files, created exclusively; historical inputs are read-only.
"""
from __future__ import annotations

import argparse
import collections
import decimal
import hashlib
import json
from pathlib import Path
import random
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/generated/v001-wind-controls-input.jsonl"
MANIFEST = ROOT / "reports/v001-wind-controls-manifest.json"
OUTPUT = ROOT / "reports/v001-wind-controls-output.jsonl"
SCORE = ROOT / "reports/v001-wind-controls-score.json"
SEED = 20261028
SELECTED = ("305", "310", "301", "302")
D = decimal.Decimal


def read(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump_new(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def target(row):
    power = [D(str(x)) for x in row["series"][1]]
    capacity = D(re.search(r"rated capacity of\s+([\d.]+)\s+MW", row["question"], re.I).group(1))
    total = sum(power)
    return total / (capacity * len(power)) * 100, total, capacity


def check_label(row):
    value, _, _ = target(row)
    matches = []
    for index, text in enumerate(row["choices"]):
        choice = D(str(text))
        tolerance = D("0.5") * D(10) ** choice.as_tuple().exponent + D("0.000001")
        if abs(value - choice) <= tolerance:
            matches.append(index)
    assert matches == [row["answer_index"]], (row["id"], matches)


def prepare():
    assert not INPUT.exists() and not MANIFEST.exists()
    parents = {r["id"]: r for r in read(ROOT / "data/source/seed100.jsonl")}
    variants = {r["parent_id"]: r for r in read(ROOT / "data/generated/counterfactuals.jsonl")
                if r["counterfactual"]["family"] == "wind_capacity_factor"
                and r["counterfactual"]["kind"] == "answer_changing"}
    rng = random.Random(SEED)
    rows, selection = [], []
    for suffix in SELECTED:
        parent_id = "tsr-numerical_reasoning-" + suffix
        parent, variant = parents[parent_id], variants[parent_id]
        before, _, _ = target(parent)
        after, _, _ = target(variant)
        base_order = list(range(4))
        rng.shuffle(base_order)
        selection.append({"parent_id": parent_id, "source_choice_index": parent["answer_index"],
                          "variant_choice_index": variant["answer_index"],
                          "source_target": str(before), "variant_target": str(after),
                          "direction": "up" if after > before else "down",
                          "base_option_order": base_order})
        for version, source in (("source", parent), ("changed", variant)):
            check_label(source)
            _, total, capacity = target(source)
            hours = len(source["series"][1])
            shared = (f"\nSampling information: each power sample represents one hour. "
                      f"The period contains {hours} hours. Rated power: {capacity} MW.")
            sum_text = f"\nComputed total actual energy output over this period: {total:.10f} MWh."
            # The rounded intermediate quantity must preserve the expected option.
            rounded_target = D(f"{total:.10f}") / (capacity * hours) * 100
            assert abs(rounded_target - target(source)[0]) < D("0.00000001")
            for arm in ("native", "native_plus_sum"):
                for rotation in range(4):
                    order = base_order[rotation:] + base_order[:rotation]
                    row = {"id": f"v001--{parent_id}--{version}--{arm}--p{rotation}",
                           "parent_id": parent_id, "task": source["task"],
                           "question": source["question"] + shared + (sum_text if arm == "native_plus_sum" else ""),
                           "choices": [source["choices"][i] for i in order],
                           "series": source["series"], "series_names": source["series_names"],
                           "answer_index": order.index(source["answer_index"]),
                           "control_experiment": {"version": version, "arm": arm,
                                                  "rotation": rotation, "source_row_id": source["id"],
                                                  "option_order": order,
                                                  "source_choice_index": source["answer_index"],
                                                  "computed_target": str(target(source)[0]),
                                                  "total_energy_mwh": f"{total:.10f}"}}
                    check_label(row)
                    rows.append(row)
    assert len(rows) == len({r["id"] for r in rows}) == 64
    assert collections.Counter(x["source_choice_index"] for x in selection) == {0: 1, 1: 1, 2: 1, 3: 1}
    assert collections.Counter(x["direction"] for x in selection) == {"up": 2, "down": 2}
    for parent_id in {r["parent_id"] for r in rows}:
        for version in ("source", "changed"):
            for arm in ("native", "native_plus_sum"):
                group = [r for r in rows if r["parent_id"] == parent_id
                         and r["control_experiment"]["version"] == version
                         and r["control_experiment"]["arm"] == arm]
                assert sorted(r["answer_index"] for r in group) == [0, 1, 2, 3]
                for original_option in range(4):
                    assert sorted(r["control_experiment"]["option_order"].index(original_option)
                                  for r in group) == [0, 1, 2, 3]
    random.Random(SEED + 1).shuffle(rows)
    tracked = subprocess.check_output(["git", "-C", str(ROOT), "ls-files", "-z"]).decode().split("\0")
    baseline = {name: sha(ROOT / name) for name in tracked if name}
    with INPUT.open("x", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    provenance_paths = [Path(__file__).resolve(), ROOT / "scripts/run_chatts_greedy.py",
                        ROOT.parent / "realtime-tslm/src/rt_tslm/runtime.py",
                        ROOT.parent / "realtime-tslm/src/rt_tslm/choice_qa.py",
                        ROOT.parent / "models/chatts-8b/processing_qwen3_ts.py",
                        ROOT.parent / "models/chatts-8b/relay-manifest.json"]
    manifest = {"experiment": "v001-wind-controls", "seed": SEED, "records": 64,
                "selection_rule": "Include 305; original labels A/B/C/D once each; earliest B-up=310, C-up=301, D-down=302; two up/two down. No model predictions used for selection. 305 was motivated by the prior audit, so this is an exploratory, not blind, sample.",
                "selection": selection, "input_sha256": sha(INPUT),
                "baseline_tracked_sha256": baseline,
                "code_sha256": {str(p.relative_to(ROOT.parent)): sha(p) for p in provenance_paths},
                "design": "4 pairs x 2 versions x 2 arms x 4 balanced rotations; identical permutations for both versions and both arms; independently shuffled call order; no preserving variants; no final-answer hints.",
                "shared_text_template": "Sampling information: each power sample represents one hour. The period contains {hours} hours. Rated power: {capacity} MW.",
                "sum_text_template": "Computed total actual energy output over this period: {total:.10f} MWh.",
                "primary_metrics": ["source/changed accuracy", "joint-correct parent/changed pairs", "correct update conditional on correct parent", "letter and numeric-choice consistency over rotations"],
                "limitations": ["Only four independent parent questions; rotations are repeated conditions, not independent samples.", "Sum arm adds a sufficient statistic and more explicit text; success does not isolate encoder internals.", "Native arm adds shared sampling metadata, so it is not an exact rerun of historical prompts.", "305 target 23.485 is on a rounding boundary; existing half-last-digit plus 1e-6 tolerance retained."]}
    dump_new(MANIFEST, manifest)
    print(json.dumps({"input": str(INPUT), "records": 64, "selection": selection}, ensure_ascii=False, indent=2))


def analyze():
    assert not SCORE.exists()
    rows, predictions = read(INPUT), read(OUTPUT)
    manifest = json.loads(MANIFEST.read_text())
    assert sha(INPUT) == manifest["input_sha256"]
    assert all(sha(ROOT / name) == value for name, value in manifest["baseline_tracked_sha256"].items())
    assert len(predictions) == 64 and [r["id"] for r in rows] == [r["id"] for r in predictions]
    sys.path.insert(0, str(ROOT / "src"))
    from cf_ts.choice_parser import parse_choice_index
    details = []
    for row, prediction in zip(rows, predictions):
        check_label(row)
        assert row["answer_index"] == prediction["expected_choice_index"]
        pred = parse_choice_index(prediction["answer"], 4)
        assert pred == prediction["predicted_choice_index"]
        first = re.match(r"^\s*([A-D])(?:[.\s:)])", prediction["answer"])
        lead = ord(first.group(1)) - 65 if first else None
        number = re.match(r"^\s*[A-D][.\s:)]+\s*([-+]?\d+(?:\.\d+)?)", prediction["answer"])
        claimed_number = number.group(1) if number else None
        c = row["control_experiment"]
        details.append({"id": row["id"], "parent_id": row["parent_id"], **c,
                        "truth": row["answer_index"], "pred": pred,
                        "pred_original_option": c["option_order"][pred] if pred is not None else None,
                        "pred_value": row["choices"][pred] if pred is not None else None,
                        "correct": pred == row["answer_index"],
                        "leading_label": lead,
                        "label_number_conflict": claimed_number is not None and pred is not None
                        and D(claimed_number) != D(str(row["choices"][pred])),
                        "stopped_on_eos": prediction["stopped_on_eos"],
                        "tokens": len(prediction["tokens"])})
    metrics, groups = {}, []
    for arm in ("native", "native_plus_sum"):
        selected = [d for d in details if d["arm"] == arm]
        matched = {}
        for d in selected:
            matched.setdefault((d["parent_id"], d["rotation"]), {})[d["version"]] = d
        pairs = list(matched.values())
        for parent in sorted({d["parent_id"] for d in selected}):
            for version in ("source", "changed"):
                g = sorted((d for d in selected if d["parent_id"] == parent and d["version"] == version), key=lambda d:d["rotation"])
                groups.append({"parent_id": parent, "arm": arm, "version": version,
                               "correct": sum(d["correct"] for d in g),
                               "letters": [d["pred"] for d in g],
                               "original_options": [d["pred_original_option"] for d in g],
                               "values": [d["pred_value"] for d in g],
                               "same_letter_all_rotations": all(d["pred"] is not None for d in g) and len({d["pred"] for d in g}) == 1,
                               "same_value_all_rotations": all(d["pred"] is not None for d in g) and len({d["pred_original_option"] for d in g}) == 1})
        metrics[arm] = {"n": len(selected), "correct": sum(d["correct"] for d in selected),
                        "source_correct": sum(d["correct"] for d in selected if d["version"] == "source"),
                        "changed_correct": sum(d["correct"] for d in selected if d["version"] == "changed"),
                        "source_n": 16, "changed_n": 16,
                        "pred_letter_counts": dict(collections.Counter(d["pred"] for d in selected)),
                        "joint_correct": sum(p["source"]["correct"] and p["changed"]["correct"] for p in pairs),
                        "pair_conditions": len(pairs),
                        "correct_parent_conditions": sum(p["source"]["correct"] for p in pairs),
                        "same_value_across_evidence": sum(p["source"]["pred_original_option"] is not None and p["source"]["pred_original_option"] == p["changed"]["pred_original_option"] for p in pairs),
                        "same_letter_groups": sum(g["same_letter_all_rotations"] for g in groups if g["arm"] == arm),
                        "same_value_groups": sum(g["same_value_all_rotations"] for g in groups if g["arm"] == arm)}
    arm_comparison = collections.Counter()
    for row in details:
        if row["arm"] != "native": continue
        other = next(d for d in details if d["arm"] == "native_plus_sum" and d["parent_id"] == row["parent_id"] and d["version"] == row["version"] and d["rotation"] == row["rotation"])
        arm_comparison[f"native_{int(row['correct'])}_sum_{int(other['correct'])}"] += 1
    result = {"records": 64, "unparsed": sum(d["pred"] is None for d in details),
              "no_eos": sum(not d["stopped_on_eos"] for d in details),
              "leading_label_mismatch": [d["id"] for d in details if d["leading_label"] != d["pred"]],
              "label_number_conflicts": [d["id"] for d in details if d["label_number_conflict"]],
              "baseline_files_unchanged": True, "metrics": metrics,
              "matched_arm_comparison": dict(arm_comparison), "rotation_groups": groups,
              "details": details, "input_sha256": sha(INPUT), "output_sha256": sha(OUTPUT)}
    dump_new(SCORE, result)
    print(json.dumps({k:v for k,v in result.items() if k not in ["details", "rotation_groups"]}, ensure_ascii=False, indent=2))
    print('ROTATION_GROUPS', json.dumps(groups, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "analyze"])
    args = parser.parse_args()
    prepare() if args.action == "prepare" else analyze()
```

</details>
