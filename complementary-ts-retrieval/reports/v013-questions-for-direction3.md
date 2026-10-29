# 方向 3 · v013：题目清单已选好，直接进入检索实验

日期：2026-10-29（北京时间）。本次只读取已有的 1,153 道题目和答案记录，没有运行模型、下载数据或修改标签。

**先用 100 道综合分析题检查“材料有没有找全”；已有的 48 道反向关系题作补充，检查两条数据的关系。两组用途不同，不把它们混成一个成绩。**

## 1. 优先使用哪 100 道题？

题库中的全部 **Insight Synthesis（综合分析）100 题**。题目同时要求：描述一个月里各个阶段如何变化，并找出明显异常。38 题有 2 个阶段，32 题有 3 个阶段，30 题有 4 个阶段；每题还保存了一个显著异常的参考记录。

例如 `L4_T1_Insight_Synthesis_00002`，需要回答 2021 年 2 月通道 71 的情况。答案包含三个阶段：先快速下降，再逐渐上升，最后快速下降；还需要指出 2 月 21 日 22:15 的一次明显下跌。

**如果选出的材料全挤在那次明显下跌附近，就可能漏掉月初、月中和月末的变化。** 这可以直接检查：检索方法是否只盯着显眼事件，还是把回答各部分所需的材料都找到了。这里“检索”就是从许多数据片段里挑出交给模型看的材料。

具体例子如下。完整 100 题列表在文末，英文原题和参考答案保存在服务器 CSV 清单中。

| 题号 | 通道 | 月份 | 要找全的内容 |
|---|---|---|---|
| `L4_T1_Insight_Synthesis_00001` | 67 | 2021-11 | 2 个变化阶段，以及明显异常和附近背景 |
| `L4_T1_Insight_Synthesis_00002` | 71 | 2021-02 | 3 个变化阶段，以及明显异常和附近背景 |
| `L4_T1_Insight_Synthesis_00004` | 123 | 2023-06 | 4 个变化阶段，以及明显异常和附近背景 |
| `L4_T1_Insight_Synthesis_00049` | HUFL | 2017-04 | 2 个变化阶段，以及明显异常和附近背景 |

这 100 题都是单变量题：适合测“回答的各部分有没有材料支持”，不直接证明跨变量的互补关系。也不把一个月的数据全部直接交给模型当作检索实验；后续应比较相同总长度下，各方法挑出的片段是否覆盖这些内容。

## 2. 另外两类现成题怎么用？

| 题目 | 数量 | 用途 |
|---|---:|---|
| 反向关系题（Causal Anomaly 中的 inverse） | 48 | 补充检查：同一时段的上下游是否一起找回、模型能否利用二者关系。具体如 `L3_T3_Causal_Anomaly_00420`、`L3_T3_Causal_Anomaly_00453` |
| 参考片段匹配题（Subsequence Matching） | 111 | 作为较简单的比较：参考片段已经给定，再找相似片段。具体如 `L2_T3_Subsequence_Matching_00331`、`L2_T3_Subsequence_Matching_00332` |

48 道反向题已全部下载，不是新增 48 道，也不能预先认为每道都必须看两条数据。111 道匹配题已有 10 道 CSV 在本地；它们不要求同时找出多个未知证据，不能当作方向 3 的全部任务。

220 道组合趋势题暂不使用，沿用此前对排名依据的疑问，不重新审计。47 道下游变平题保留作简单检查，不再围绕它们扩展模型实验。其余 627 题本轮不优先。以上分类覆盖全部 1,153 道，不是只看了几个例子。

当前题型中，没有发现要求系统从许多通道里自行找出应配对对象的明确题型；不能把已有上下游题当作这种能力的测试。

## 3. 下一步直接做什么？

用这 100 道综合分析题准备片段检索比较：一组按单个片段与问题的相关程度选；一组增加片段数量；一组按题目要求兼顾各阶段和异常。先记录各方法实际拿回哪些材料，再比较回答是否完整。增加片段数量的一组要单独报告多用了多少数据。

另外提供一组由参考答案帮助确定的完整材料，检查“材料齐全时模型能否回答”。它只是帮助区分找材料和回答这两步的对照，不能算检索方法自己的成绩。

**这一步的论文价值是检查：在同样允许读取的数据量下，现有检索是否会反复找同一类材料、遗漏其他必需内容。** 如果简单规则就能解决，应保留它作为重要比较对象；本清单不宣称发现了新问题或新方法。

100 道综合题的原始 CSV 目前尚未下载。下一步先下载这 100 道现有发布数据，再准备检索比较；本次没有执行下载或新推理。

## 4. 清单和原始题目在哪里？

服务器项目目录：`/root/autodl-tmp/cf-run/TSQA_ideas/complementary-ts-retrieval/`。

| 文件 | 内容 |
|---|---|
| `results/v013-question-shortlist/primary100-insight.csv` | 全部 100 道优先题：题号、月份、阶段数、所需材料、英文原题、原参考答案和 CSV 文件名 |
| `results/v013-question-shortlist/aux48-inverse.csv` | 全部 48 道补充题及对应上下游材料 |
| `results/v013-question-shortlist/all1153-question-inventory.csv` | 全部 1,153 道题的分类和用途 |
| `results/v013-question-shortlist/selection-summary.json` | 数量核对、原文件校验和本地 CSV 是否存在 |
| `data/metadata/tasks-99866c43cd7ceb91a929de745e9f49cea92962e5.json` | 未修改的原题目与答案文件 |

清单中的参考答案只供研究核对，不能混入检索提示或用于计算候选相关性。按仓库约定，Git 只提交本报告，清单保存在服务器。

<details>
<summary>展开全部 100 道优先题的题号</summary>

| 完整题号 | 通道 | 月份 | 变化阶段数 |
|---|---|---|---:|
| `L4_T1_Insight_Synthesis_00001` | 67 | 2021-11 | 2 |
| `L4_T1_Insight_Synthesis_00002` | 71 | 2021-02 | 3 |
| `L4_T1_Insight_Synthesis_00003` | 99 | 2021-12 | 2 |
| `L4_T1_Insight_Synthesis_00004` | 123 | 2023-06 | 4 |
| `L4_T1_Insight_Synthesis_00009` | 154 | 2022-03 | 3 |
| `L4_T1_Insight_Synthesis_00011` | 166 | 2023-07 | 2 |
| `L4_T1_Insight_Synthesis_00012` | 169 | 2023-07 | 4 |
| `L4_T1_Insight_Synthesis_00014` | 172 | 2019-06 | 2 |
| `L4_T1_Insight_Synthesis_00015` | 173 | 2022-01 | 4 |
| `L4_T1_Insight_Synthesis_00016` | 177 | 2022-11 | 3 |
| `L4_T1_Insight_Synthesis_00019` | 312 | 2019-03 | 2 |
| `L4_T1_Insight_Synthesis_00020` | 430 | 2019-07 | 3 |
| `L4_T1_Insight_Synthesis_00021` | 441 | 2023-11 | 3 |
| `L4_T1_Insight_Synthesis_00024` | 501 | 2021-05 | 3 |
| `L4_T1_Insight_Synthesis_00026` | 580 | 2022-12 | 2 |
| `L4_T1_Insight_Synthesis_00027` | 589 | 2022-03 | 2 |
| `L4_T1_Insight_Synthesis_00029` | 595 | 2019-07 | 4 |
| `L4_T1_Insight_Synthesis_00031` | 626 | 2021-07 | 4 |
| `L4_T1_Insight_Synthesis_00033` | 647 | 2021-05 | 3 |
| `L4_T1_Insight_Synthesis_00034` | 680 | 2019-12 | 4 |
| `L4_T1_Insight_Synthesis_00035` | 683 | 2023-01 | 2 |
| `L4_T1_Insight_Synthesis_00036` | 727 | 2019-04 | 2 |
| `L4_T1_Insight_Synthesis_00037` | 728 | 2020-07 | 4 |
| `L4_T1_Insight_Synthesis_00038` | 729 | 2023-07 | 3 |
| `L4_T1_Insight_Synthesis_00041` | 811 | 2022-12 | 2 |
| `L4_T1_Insight_Synthesis_00045` | 894 | 2023-12 | 3 |
| `L4_T1_Insight_Synthesis_00046` | 895 | 2022-03 | 4 |
| `L4_T1_Insight_Synthesis_00049` | HUFL | 2017-04 | 2 |
| `L4_T1_Insight_Synthesis_00050` | MUFL | 2018-03 | 2 |
| `L4_T1_Insight_Synthesis_00051` | LULL | 2017-10 | 4 |
| `L4_T1_Insight_Synthesis_00053` | 67 | 2019-01 | 3 |
| `L4_T1_Insight_Synthesis_00054` | 71 | 2022-01 | 4 |
| `L4_T1_Insight_Synthesis_00055` | 99 | 2019-03 | 4 |
| `L4_T1_Insight_Synthesis_00056` | 123 | 2023-12 | 4 |
| `L4_T1_Insight_Synthesis_00057` | 124 | 2021-01 | 2 |
| `L4_T1_Insight_Synthesis_00061` | 154 | 2019-04 | 2 |
| `L4_T1_Insight_Synthesis_00062` | 155 | 2023-06 | 4 |
| `L4_T1_Insight_Synthesis_00065` | 170 | 2019-01 | 3 |
| `L4_T1_Insight_Synthesis_00066` | 172 | 2020-08 | 4 |
| `L4_T1_Insight_Synthesis_00067` | 173 | 2021-10 | 2 |
| `L4_T1_Insight_Synthesis_00069` | 237 | 2020-02 | 3 |
| `L4_T1_Insight_Synthesis_00070` | 245 | 2022-07 | 3 |
| `L4_T1_Insight_Synthesis_00073` | 441 | 2022-05 | 3 |
| `L4_T1_Insight_Synthesis_00074` | 495 | 2023-09 | 2 |
| `L4_T1_Insight_Synthesis_00075` | 496 | 2021-01 | 2 |
| `L4_T1_Insight_Synthesis_00076` | 501 | 2022-03 | 2 |
| `L4_T1_Insight_Synthesis_00079` | 589 | 2022-07 | 2 |
| `L4_T1_Insight_Synthesis_00080` | 591 | 2019-04 | 2 |
| `L4_T1_Insight_Synthesis_00081` | 595 | 2023-04 | 2 |
| `L4_T1_Insight_Synthesis_00083` | 626 | 2021-01 | 4 |
| `L4_T1_Insight_Synthesis_00086` | 680 | 2019-04 | 4 |
| `L4_T1_Insight_Synthesis_00090` | 729 | 2019-09 | 3 |
| `L4_T1_Insight_Synthesis_00091` | 754 | 2022-09 | 4 |
| `L4_T1_Insight_Synthesis_00092` | 762 | 2019-11 | 2 |
| `L4_T1_Insight_Synthesis_00093` | 811 | 2020-07 | 3 |
| `L4_T1_Insight_Synthesis_00096` | 891 | 2020-08 | 3 |
| `L4_T1_Insight_Synthesis_00097` | 894 | 2022-06 | 2 |
| `L4_T1_Insight_Synthesis_00098` | 895 | 2022-05 | 4 |
| `L4_T1_Insight_Synthesis_00099` | 897 | 2023-03 | 3 |
| `L4_T1_Insight_Synthesis_00102` | MUFL | 2016-09 | 2 |
| `L4_T1_Insight_Synthesis_00104` | LULL | 2016-07 | 2 |
| `L4_T1_Insight_Synthesis_00105` | OT | 2017-09 | 3 |
| `L4_T1_Insight_Synthesis_00107` | 71 | 2023-09 | 3 |
| `L4_T1_Insight_Synthesis_00108` | 99 | 2019-05 | 3 |
| `L4_T1_Insight_Synthesis_00110` | 124 | 2023-01 | 4 |
| `L4_T1_Insight_Synthesis_00112` | 147 | 2023-10 | 4 |
| `L4_T1_Insight_Synthesis_00113` | 151 | 2021-09 | 3 |
| `L4_T1_Insight_Synthesis_00114` | 154 | 2022-12 | 3 |
| `L4_T1_Insight_Synthesis_00115` | 155 | 2021-02 | 2 |
| `L4_T1_Insight_Synthesis_00116` | 166 | 2020-03 | 2 |
| `L4_T1_Insight_Synthesis_00117` | 169 | 2023-03 | 4 |
| `L4_T1_Insight_Synthesis_00118` | 170 | 2020-06 | 3 |
| `L4_T1_Insight_Synthesis_00119` | 172 | 2022-01 | 4 |
| `L4_T1_Insight_Synthesis_00120` | 173 | 2020-11 | 4 |
| `L4_T1_Insight_Synthesis_00122` | 237 | 2019-04 | 3 |
| `L4_T1_Insight_Synthesis_00123` | 245 | 2020-05 | 3 |
| `L4_T1_Insight_Synthesis_00124` | 312 | 2022-05 | 3 |
| `L4_T1_Insight_Synthesis_00125` | 430 | 2020-01 | 2 |
| `L4_T1_Insight_Synthesis_00127` | 495 | 2022-09 | 2 |
| `L4_T1_Insight_Synthesis_00130` | 578 | 2023-01 | 4 |
| `L4_T1_Insight_Synthesis_00132` | 589 | 2019-06 | 2 |
| `L4_T1_Insight_Synthesis_00133` | 591 | 2020-11 | 4 |
| `L4_T1_Insight_Synthesis_00134` | 595 | 2022-04 | 2 |
| `L4_T1_Insight_Synthesis_00135` | 625 | 2021-10 | 2 |
| `L4_T1_Insight_Synthesis_00137` | 627 | 2021-08 | 3 |
| `L4_T1_Insight_Synthesis_00140` | 683 | 2020-04 | 2 |
| `L4_T1_Insight_Synthesis_00141` | 727 | 2021-10 | 3 |
| `L4_T1_Insight_Synthesis_00142` | 728 | 2019-08 | 4 |
| `L4_T1_Insight_Synthesis_00144` | 754 | 2023-11 | 4 |
| `L4_T1_Insight_Synthesis_00145` | 762 | 2020-12 | 2 |
| `L4_T1_Insight_Synthesis_00146` | 811 | 2019-11 | 4 |
| `L4_T1_Insight_Synthesis_00147` | 813 | 2021-05 | 4 |
| `L4_T1_Insight_Synthesis_00148` | 865 | 2021-10 | 2 |
| `L4_T1_Insight_Synthesis_00149` | 891 | 2023-02 | 2 |
| `L4_T1_Insight_Synthesis_00150` | 894 | 2022-03 | 2 |
| `L4_T1_Insight_Synthesis_00151` | 895 | 2022-05 | 4 |
| `L4_T1_Insight_Synthesis_00152` | 897 | 2023-09 | 3 |
| `L4_T1_Insight_Synthesis_00153` | 933 | 2021-10 | 3 |
| `L4_T1_Insight_Synthesis_00154` | HULL | 2016-08 | 2 |
| `L4_T1_Insight_Synthesis_00155` | MULL | 2018-06 | 3 |

</details>
