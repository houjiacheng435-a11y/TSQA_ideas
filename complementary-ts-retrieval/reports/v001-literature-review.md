# 方向 3 · v001：互补时序证据检索的文献与重复风险审查

检索日期：2026-10-28。范围：通用证据集合检索、基于已有证据的补充检索、时序片段选择、多变量模式搜索与预算约束。本次没有下载模型或实验数据，没有运行模型、训练或生成新题。

## 1. 先看结论

**方向 3 当前的宽泛设想重复风险较高，还不能直接作为新方法立项。**

已经找到直接方法先例：从逐段排名转为整组证据选择、学习问题与证据集合的匹配分数、根据已有证据检索缺失信息，以及在有限预算下组合时序证据，都有相关工作。

但这不意味着所有时序关系检索问题已经解决。合理的下一步是：明确一个现有方法没有充分解决的具体问题，完成强基线比较，再决定是否提出新方法。仅把文本证据换成时序、把检索器换成 Set Transformer 或 JEV-style 模型，尚不能构成充分贡献。

本报告是针对性查新，不是覆盖全部论文的系统综述，也不提供“从未有人做过”的保证。全文保留论文英文原名；中文是内容解释及项目判断，没有改写英文引文。

## 2. 原设想中哪些已有直接先例

| 我们原本考虑的想法 | 已找到的先例 | 当前处理 |
|---|---|---|
| 不只看单段相关性，而看整组证据是否完整 | SetR、OptiSet | 作为已有思想及基线 |
| 训练一个问题—证据集合评分器 | ParaSet / SetCE | 与原文档的集合评分方法直接重合 |
| 看过一段后，寻找当前缺少的互补信息 | GRAIL；时序侧有 ARTIST、TSHarness 的相关机制 | 不能把“根据已有证据继续找”本身作为新意 |
| 在少量证据预算下组合时序窗口 | Tree-of-Evidence、TimeSeg | 必须区分预测解释与查询求解目标，并比较方法 |
| 处理多变量模式和通道之间的时间错位 | SAXRegEx | 时间匹配本身已有经典算法研究 |
| 在长时序中按自然语言搜索并用程序验证 | Sonar-TS；形状表示还有 TT-SAX | 不能把整体流程作为新贡献 |

“已有先例”表示核心思想或方法已公开，不表示该方法在我们的任务上一定有效或已经达到完美性能。

## 3. 通用检索：原方法设想的主要重复风险

### 3.1 SetR：先分解证据需求，再选择完整集合

**英文原名：** `Shifting from Ranking to Set Selection for Retrieval Augmented Generation`

Lee et al.，ACL 2025。SetR 利用推理识别问题的信息需求，再选择共同满足需求的一组材料，并在多步问答中评估。已核对官方摘要、出版信息，并打开正式论文。[ACL 原文](https://aclanthology.org/2025.acl-long.861/)

**对本项目的影响：** “相关片段不等于完整证据，需要按照问题的需求选集合”已有清晰先例。后续不能只比较普通 Top-K 而省略这种方法。

### 3.2 ParaSet / SetCE：直接学习集合匹配，而非独立得分相加

**最新英文原名：** `Scoring a Set, Not Summing Passage Scores: Effective and Efficient Set Retrieval`

Song and Lee，arXiv:2607.05712，2026-09-28 v2。直接学习问题与完整证据集合的兼容分数；通过增添、删除和替换材料构造训练对比。ParaSet 在预计算表示上做轻量集合评分，SetCE 对候选集合进一步重排。已核对正文 §3 及候选集合搜索相关附录。[原文](https://arxiv.org/html/2607.05712v2)

**对本项目的影响：** 原文档提出的“问题＋已有证据＋候选片段，学习组合价值”不能直接视为新方法。即使采用轻量注意力或缓存集合表示，也需要具体区别。

版本说明：该 arXiv 编号的早期标题为 `Retrieving a Set, Not Independent Passages: Set-Level Compatibility Learning for Efficient Set Exploration`。这是同一工作的不同版本，不能算两篇独立先例。

### 3.3 GRAIL：检索已有证据之外缺少的部分

**英文原名：** `Subtraction Gets You More: Gap-Aware Retrieval for Multimodal Multi-Hop QA`

O and Lee，arXiv:2605.28641，2026-10-19 v3。研究证据集合补全与逐步建立检索池，指出已有上下文可能导致重复检索；在向量空间抑制已经覆盖的方向，引导搜索缺失证据。已核对问题定义、方法、实验及限制部分。[原文](https://arxiv.org/html/2605.28641v3)

**对本项目的影响：** “找到了价格下跌后，应寻找成交量信息而非更多下跌片段”与其研究动机相近。它主要研究文本、图片和表格材料，并不等于解决了连续时序关系检索；但直接搬用其思路仍需说明新增困难。

### 3.4 OptiSet：用生成器的集合效用变化识别互补性

**英文原名：** `OptiSet: Unified Optimizing Set Selection and Ranking for Retrieval-Augmented Generation`

Jiang et al.，arXiv:2601.05027，2026-01。采用扩展后精炼的集合流程，并利用给定证据集合后生成器效用的变化构造偏好监督。此处核对至官方摘要，未逐项复核实验。[论文](https://arxiv.org/abs/2601.05027)

**对本项目的影响：** “加入候选后能否提高回答质量”作为互补性训练信号，也有直接先例；不能只替换输入模态就宣称信号本身是新提出的。

### 3.5 QUBO：把互补、覆盖与预算写入集合选择目标

**英文原名：** `QUBO-Optimized Evidence Selection for Retrieval-Augmented Question Answering with Unconventional Solvers`

Singh and Vadlamani，arXiv:2607.12334，2026-07。将材料相关性、需求覆盖、互补性、冗余及集合规模等写入离散优化目标。已核对方法 §3 与消融表；其额外目标项并非都带来更好的答案表现。[原文](https://arxiv.org/html/2607.12334v1)

**对本项目的影响：** 给相关性加上互补奖励、冗余惩罚和预算项，属于已有方法族。后续应避免把公式项增多本身当作贡献。

## 4. 时序领域：需要直接面对的工作

### 4.1 ARTIST：累计片段条件下的动态选择

**英文原名：** `Adaptive Time Series Reasoning via Segment Selection`

Messica et al.，ICML 2026。选择器根据问题、累计片段及中间推理选择下一段或停止；正文 §3.1 明确采用单变量设置。已核对方法；出版状态及代码参见官方项目。[论文](https://arxiv.org/html/2602.18645v3)、[官方项目](https://zitniklab.hms.harvard.edu/ARTIST/)

**当前区别：** 我们希望研究跨变量及其时间关系；但“单变量改成多变量”是否构成实质贡献，需要实验和方法证据。复现时还必须核对各角色是否已接触完整输入，不能仅用返回片段数量代表全部信息预算。

### 4.2 TSHarness：证据缺口检查与针对性补充

**英文原名：** `Zero-Shot Time-Series Question Answering via Decoupled Perception and Reasoning`

Xie et al.，arXiv:2610.04942，2026-10。根据问题建立所需证据类型，维护数值感知状态，检查缺口并请求带变量、操作和参数的补充分析。已核对方法 §3.3–3.5 和附录 B.4。[原文](https://arxiv.org/html/2610.04942v1)

**当前区别：** 它侧重工具分析结果的覆盖与跨任务回答，不直接等同于大规模片段库中的集合检索。它已经使“发现缺证据并补齐”成为必须比较的已有能力。

### 4.3 Sonar-TS：长历史搜索、跨通道任务与数值核验

**英文原名：** `Sonar-TS: Search-Then-Verify Natural Language Querying for Time Series Databases`

Tan et al.，ICML 2026 官方实现。搜索候选窗口后用程序核验；NLQTSBench 已包括跨通道异常等任务。已核对正文、附录任务描述与官方实现说明。[论文](https://arxiv.org/html/2602.17001v3)、[官方仓库](https://github.com/Atlamtiz/Sonar-TS)

**当前区别：** 我们尚未提出或验证超出这一流程的方法。它的失败可能来自模式表示、查询转换、候选遗漏或核验程序；看到跨通道题答错，不足以断定证据组合是瓶颈。

### 4.4 LaSTR：语言与局部时序片段匹配

**英文原名：** `LaSTR: Language-Driven Time-Series Segment Retrieval`

Dohi et al.，arXiv:2603.00725，2026-02。利用片段描述训练对比检索器，主要设置为单变量候选片段与单个正例检索。已核对问题定义与评测设置。[原文](https://arxiv.org/html/2603.00725v1)

**当前区别：** 相比集合任务，它更接近第一阶段片段匹配；可以提供参考基线。其设置较窄不能作为整个领域没有联合检索工作的证据。

### 4.5 Tree-of-Evidence：时序证据集合搜索已经有直接实现

**英文原名：** `Tree-of-Evidence: Efficient "System 2" Search for Faithful Multimodal Grounding`

Nnamdi et al.，Findings of ACL 2026。对时序窗口及文本块选择紧凑组合，使用 beam search，目标包含原预测的一致性、概率稳定性与证据成本，并与逐段 Top-K 比较。已核对论文 §3.4、实验及限制。[官方页面](https://aclanthology.org/2026.findings-acl.1460/)

**关键区别：** 它主要解释并复现已有模型的预测；我们希望证据足以正确回答用户的查询。两种目标不同，原预测也可能有错。然而这种目标区别只是值得核查的研究出发点，尚不是已证明的新贡献。

### 4.6 TimeSeg：联合信息量驱动的片段选择

**英文原名：** `TimeSeg: An Information-Theoretic Segment-Wise Explainer for Time-Series Predictions`

Kim et al.，ICLR 2026。将解释定义为选择与目标预测具有较高联合信息量的连续片段，并转化为顺序选择。核对至官方摘要与公开论文中的方法描述。[正式出版页面](https://proceedings.iclr.cc/paper_files/paper/2026/hash/f4fba41b554f9aaa013c4062a1c40518-Abstract-Conference.html)

**当前区别：** 固定预测任务的解释，与自然语言条件下的证据搜索不是同一任务；但“根据已选片段的条件信息价值继续选择”不能视为全新的原理。

### 4.7 SAXRegEx：多变量模式及通道间时间延迟并非空白

**英文原名：** `Multivariate Time Series Retrieval with Symbolic Aggregate Approximation, Regular Expression, and Query Expansion`

Yu, Becker and Behrisch，EuroVA 2022。作者将该方法称为 SAXRegEx，使用符号表示、正则表达式与查询扩展，处理多变量模式的时长变化及通道间时间延迟。已核对出版方摘要和公开会议论文。[出版方页面](https://diglib.eg.org/items/41c7ca54-4e11-4585-98c6-8e2205b002ed)

2023 年期刊扩展版题为 `SAXRegEx: Multivariate time series pattern search with symbolic representation, regular expression, and query expansion`；本次未能直接打开其全文，不将期刊版当作已精读材料。[期刊元数据](https://www.sciencedirect.com/science/article/pii/S0097849323000316)

**当前区别：** 主要是示例和可视化查询，不能直接等同于任意自然语言检索；它提示我们必须面对传统多变量搜索与时间匹配基线。

### 4.8 TT-SAX：NLQTSBench 上的低表现可能来自模式表示

**英文原名：** `TT-SAX: A Two-Track Time Series Symbolization for Natural Language Shape Querying`

Tan et al.，arXiv:2610.30593，2026-10-22。面向自然语言形状查询改造符号表示，保留水平信息并补充与查询尺度匹配的趋势信息，在 NLQTSBench 复合趋势任务评测。已核对正文设计和实验范围。[原文](https://arxiv.org/html/2610.30593v1)

**容易误读之处：** Two-Track 指水平与趋势两种符号轨道，不等于两个传感器变量。不能据标题就认为它研究了全部跨通道组合问题。

**对本项目的影响：** 不能把 Sonar-TS 的复合趋势失误自动解释为缺乏互补证据；需要先检查单段表示与候选召回是否足够。

## 5. 邻近文献：防止把术语相同误认为任务相同

| 英文原名 | 核对范围及与本项目的关系 |
|---|---|
| `FreshCast: Timely and Complementary Retrieval for Frozen Time Series Forecasters` | 2026-10 预印本，核对官方摘要；互补性主要指检索修正能否补偿预测器残差，是未来数值预测，不是为用户问题寻找完整证据。[论文](https://arxiv.org/abs/2610.07834v3) |
| `Learning to Select Source-Traceable Evidence for Language-Model Prediction from Irregular Clinical Time Series` | STEP-CTS，2026-09 修订预印本，核对官方摘要；选择带来源窗口的数值谓词及临床概念，服务固定预测任务。可作为可溯源证据构造的邻近工作。[论文](https://arxiv.org/abs/2605.20292v2) |

本报告核对 15 项工作：第 3 节五项、第 4 节八项、第 5 节两项。SAXRegEx 会议版与期刊扩展版只算一个工作，ParaSet 的不同标题版本也只算一个。预印本与正式出版状态在各项中分别标注，未把所有 arXiv 论文都当作已录用论文。

## 6. 原方向的哪些表述应当调整

### 不宜继续作为核心创新表述

- “我们首次发现 Top-K 会遗漏互补证据。”
- “我们首次根据已有证据寻找缺失片段。”
- “我们首次学习证据集合的评分函数。”
- “我们首次在预算限制下选择时序证据集合。”
- “把时间关系加入评分，再换成 JEV 或 Set Transformer，就是新方法。”

这些表述与已找到的方法重合，或缺少能支持“首次”的证据。它们仍可以作为已有模块和必要基线。

### 可以核查，但尚未确认有新意的具体问题

**候选问题：在单段形状都能正确识别的前提下，跨变量的实体对应、时间顺序和允许延迟，是否仍导致通用集合检索器稳定选择错误组合？**

例如温升与压力峰值都被找到，但来自不同设备或不匹配的时间段。这个例子本身不新；价值取决于：现有集合方法与传统时间关联算法是否真的失败，以及我们能否针对失败提出有解释力的改进。

要特别区分：

1. **数据真的不够。** 第一阶段没有找回某段，集合重排无法凭空补回。
2. **单段识别不准。** 把波动当趋势或遗漏短峰值，属于感知与表示问题。
3. **组合关系判断错。** 单段识别与候选召回都足够，仍选了时间或实体关系不成立的集合。
4. **答案生成错。** 已经提供有效证据组合，最终回答仍错。

只有第三项的稳定存在，才直接支持当前想研究的组合选择瓶颈。不能只根据最终答案错误就宣称找到了它。

还应注意：若单段事件都已被准确识别，所需变量、时间顺序和延迟条件也完全明确，数据库时间关联往往就能完成组合。不能为了让学习模型显得必要而禁止这种基线，或人为制造它无法使用的信息差。学习方法的必要性仍需单独证明。

## 7. 继续前必须补上的基线与证据

| 比较 | 要回答的问题 |
|---|---|
| 单段 Top-K、去重、多样性排序 | 是否只是重复片段过多 |
| 按变量覆盖分配名额 | 是否只是没找齐不同变量 |
| 事件检测＋时间邻域匹配／时间关联 | 简单数值规则是否已经能找对组合 |
| SetR 或同类需求驱动集合选择 | 通用集合方法能否直接适用 |
| ParaSet / SetCE 思路及逐步检索 | 是否真的需要新的集合评分，而不是迁移已有方法 |
| Sonar-TS；适用子任务中的更强符号表示 | 失败是否先发生在模式表达或候选生成 |
| 人工核实的有效证据集合＋同一回答器 | 排除证据足够但回答器不可靠的影响 |

公平比较需要说明每个角色能看到什么、索引保留什么，以及真实读取点数、模型调用和离线计算成本。只把返回的片段数固定，不能保证信息和计算预算相同。

若使用合成诊断题，必须避免答案由时间戳、变量名或显著性捷径直接暴露。允许多组有效证据；不能把不同于某一人工标注的集合一概判错。构造数据前需要明确授权，本次没有执行。

## 8. 对下一步的建议

**当前阶段保留问题探索，暂不开始设计或训练集合模型。**

1. 优先进一步对照 SetR、ParaSet / SetCE、Tree-of-Evidence 与我们的具体任务定义，记录已有目标、监督信号和评价方式。
2. 如继续核验 NLQTSBench 的开发案例，目的应是定位失败环节，不能把两道题的错误作为新方法立项证据。下载、调用 API、GPU 推理和新数据构造均需另行说明后执行。
3. 若在清楚定义的关系任务上，简单时间关联或通用集合选择已经足够，应调整研究问题，不额外设计复杂模型。
4. 若单段识别、候选召回均正常，但强基线仍稳定选错组合，再讨论是否需要学习关系约束，以及如何在新设备、时间范围和关系类型上验证。

本文判断是：**方向 3 的原始方法轮廓已有较多先例；一个更具体的时序关系问题仍可能值得研究，但当前还没有确认足以支撑论文的新贡献。**

## 9. 检索与核对记录

检索通过论文官网、arXiv、ACL Anthology、ICLR proceedings 和 Eurographics Digital Library 等原始来源完成。搜索结果与二手摘要只用于发现线索，核心判断回到原始来源核对。

代表性查询包括：`time series evidence joint retrieval`、`time series complementary retrieval`、`evidence set retrieval complementarity question answering`、`time series segment selection multivariate`、`time series cross-channel retrieval`、`multivariate time series temporal pattern search`，并追踪集合选择论文中 SetR、OptiSet 等引用。

核对深度已逐项标注。报告没有把“打开论文”当作“复现或验证其结论”，也没有声称已经独立验证作者报告的收益。期刊全文访问受限处已说明，未用二手评论补充为既成事实。

本报告保存在总仓库的方向 3 独立目录 `complementary-ts-retrieval/reports/`。本次仅新增报告，不修改方向 1 文件、README、历史实验数据或模型环境。
