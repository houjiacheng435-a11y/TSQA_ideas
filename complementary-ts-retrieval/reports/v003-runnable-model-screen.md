# 方向 3 · v003：优先选择无需重新训练的公开模型

核对日期：2026-10-28。本轮只检查官方网页、源码、公开文件元数据及本地软件版本；没有下载模型权重、安装依赖、调用模型 API、运行 GPU 或修改实验数据。

## 1. 选择结果

**新增时序模型优先选择 TimeOmni-1-7B；保留已经在服务器跑通的 ChatTS-8B；Qwen3-8B 作为通用语言模型对照。** Sonar-TS 保留为直接相关的搜索与核验系统，但其官方运行需要 API 密钥及费用授权。

这份清单中的“无需训练”表示可使用已经公开的权重或冻结模型进行推理，不代表所有模型已经在本服务器完成实测，也不代表它们天然支持我们选定的任务格式。

## 2. 已核实的候选

| 候选 | 公开资源 | 本服务器上的状态 | 第一轮用途 |
|---|---|---|---|
| ChatTS-8B | 完整权重、原生时序处理器和代码 | 本地已有，之前已跑通；方向 3 尚未运行 | 原生时序输入的回答模型 |
| TimeOmni-1-7B | 作者官方仓库链接到公开完整权重，标准 Qwen2 架构，有单题推理入口 | 未下载完整权重；现有 Transformers 可识别该架构，尚未做本机推理验证 | 新增的文献时序推理模型，采用数值文本输入 |
| Qwen3-8B | 完整公开权重、标准推理接口 | 未下载完整权重；现有 Transformers 版本满足官方架构支持要求 | 通用模型对照，不当作新的证据检索方法 |
| Sonar-TS | 完整搜索、代码生成与执行流程；针对 NLQTSBench | 官方默认调用 DeepSeek API，需要密钥、数据索引与费用授权 | 直接相关的现有系统，检查候选生成和核验过程 |

来源：[ChatTS-8B](https://huggingface.co/bytedance-research/ChatTS-8B)、[TimeOmni-1 官方仓库](https://github.com/AntonGuan/TimeOmni-1)、[TimeOmni-1-7B 权重](https://huggingface.co/anton-hugging/TimeOmni-1-7B)、[Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B)、[Sonar-TS](https://github.com/Atlamtiz/Sonar-TS)。

TimeOmni-1 是回答模型，不是证据集合检索器。新增它可以检查现象是否超出 ChatTS，但**不能替代 ARTIST、SetR 或 ParaSet 对研究问题的比较作用**。这些方法缺少可用复现材料时，应明确留下比较缺口，不能把缺口解释成已有方法失败。

## 3. TimeOmni-1-7B 为什么优先

公开模型 ID 为 `anton-hugging/TimeOmni-1-7B`。本次 Hugging Face API 返回：

- revision：`22ae9bf80572bd309d5926b66d608754c53172a0`。
- `private=false`、`gated=false`，即公开且未设置申请访问门槛。
- 四个完整 `safetensors` 权重分片，共 **15,231,271,896 字节，约 15.23 GB**；tokenizer 和配置另外占少量空间。
- 架构为 `Qwen2ForCausalLM`，不要求重新训练时序编码器。

这些信息来自公开文件清单，没有下载权重或计算权重文件指纹。[公开文件清单](https://huggingface.co/anton-hugging/TimeOmni-1-7B/tree/22ae9bf80572bd309d5926b66d608754c53172a0)

本服务器当前包版本为 PyTorch `2.6.0+cu124`、Transformers `4.52.4`、Accelerate `1.10.1`。7B 模型的参数规模表明，限制上下文长度、使用半精度、逐题推理时值得在 24GB 卡上做小规模验证；**这只是容量估计，尚没有本机峰值显存或速度测量**。

必须处理的两个具体问题：

1. **环境版本。** 最新官方仓库已经加入基于 Qwen3.5 的 4B/9B 模型，其依赖文件要求 Transformers ≥5.6.0 和 vLLM ≥0.19.0，不能整套安装到现有 ChatTS 环境。7B 的旧官方入口在 commit `8edac8994f5985def35bb8633594c7a8d5b95835` 使用标准 `AutoModelForCausalLM`。后续可保留其提示与生成设置，使用现有版本的半精度加载参数准备轻量运行器；这属于推理接口适配，不是训练或更改权重。旧入口默认加载没有显式指定半精度，因此也不能不检查就直接照抄到 24GB 卡上。
2. **输出格式。** 官方默认单题提示要求输出选项字母；NLQTSBench 的许多题要求时间区间或日期集合。后续需要明确记录格式提示适配，并先检查能否输出这些答案类型。不能把持续输出字母的格式失败算成证据组合失败，也不为迁就模型而把原题改成选择题。

来源：[最新依赖文件](https://github.com/AntonGuan/TimeOmni-1/blob/main/requirements.txt)、[7B 旧官方推理入口](https://github.com/AntonGuan/TimeOmni-1/blob/8edac8994f5985def35bb8633594c7a8d5b95835/inference/inference.py)。源码仅做了静态阅读与语法解析，没有执行远程代码。

## 4. 前面提到的证据选择方法，哪些暂时不能直接用

| 方法 | 本次找到什么 | 决定 |
|---|---|---|
| ARTIST | 官方代码和配置已公开；README 的推理例子要求本地训练后 checkpoint 路径，未找到官方可直接下载的 SFT/RL 权重；公开 issue #1 也在请求相关材料，本次 API 返回无评论 | 暂不列入可直接推理清单；不自行重训 |
| SetR | 官方流程提供数据构造和训练；未找到官方训练后模型下载链接；请求发布权重的 issue #1 本次无评论 | 暂缓完整模型复现；若以后使用原文提示搭配 Qwen，须标注为提示流程适配 |
| LaSTR | 官方项目页当前文件清单只有 README，提供描述生成和评价提示，没有可运行检索器源码或训练后检索器下载链接 | 暂缓，不能把项目页当作已发布模型 |
| ParaSet / SetCE | 论文公开了方法与训练细节，本次未确认作者提供的可下载权重及完整运行包 | 暂缓；本次检索不构成“任何地方都没有权重”的证明 |

来源：[ARTIST 官方仓库](https://github.com/mims-harvard/ARTIST)、[ARTIST 材料请求](https://github.com/mims-harvard/ARTIST/issues/1)、[SetR 官方仓库](https://github.com/LGAI-Research/SetR)、[SetR 权重发布请求](https://github.com/LGAI-Research/SetR/issues/1)、[LaSTR 官方项目页](https://github.com/Kota-Dohi/LaSTR)、[ParaSet / SetCE 论文](https://arxiv.org/html/2607.05712v2)。结论限于本次检查到的公开入口；未联系作者，没有发送消息或发布 issue。

OpenTSLM 也有公开训练后文件，例如 `OpenTSLM/llama-3.2-1b-tsqa-sp`。但它的两个 `.pt` 文件各约 28.60 MB，加载器还会单独加载基础语言模型；并非只下载这个小文件就能推理。该版本依赖 `meta-llama/Llama-3.2-1B` 的访问条件，最新项目依赖还要求 PyTorch ≥2.9.1、Transformers ≥4.57.3。因此将它保留为备选，暂不优先处理权限和新环境。[OpenTSLM 加载器](https://github.com/OpenTSLM/OpenTSLM/blob/main/src/opentslm/model/llm/OpenTSLM.py)、[SP 实现](https://github.com/OpenTSLM/OpenTSLM/blob/main/src/opentslm/model/llm/OpenTSLMSP.py)、[依赖](https://github.com/OpenTSLM/OpenTSLM/blob/main/requirements.txt)、[基础模型访问页](https://huggingface.co/meta-llama/Llama-3.2-1B)。

## 5. Sonar-TS 的可运行性与限制

它没有要求我们训练一个新模型，但官方默认通过 `DeepSeekClient` 调用 `deepseek-v4-flash`，需要 API 密钥与调用费用。数据预处理和程序执行也有 CPU 成本，不能把它描述成“无成本”。本次只阅读接口，没有检查用户密钥、发出推理请求或构建索引。[API 客户端](https://github.com/Atlamtiz/Sonar-TS/blob/main/sonar_ts/llm.py)、[在线配置](https://github.com/Atlamtiz/Sonar-TS/blob/main/configs/online.yaml)

配置中虽有 `base_url` 和 `model` 字段，但这不能证明任意本地模型能直接替换。若以后替换为 Qwen，须核验请求兼容和工具行为，并报告为更换骨干的适配实验。当前没有把该适配计作原系统已经跑通。

## 6. 下一步的具体边界

1. 继续只读筛查任务，固定题号、证据需求和输出类型。
2. 新增模型优先只申请下载 TimeOmni-1-7B，约 15.23 GB 权重；ChatTS 复用本地文件。Qwen3-8B 若随后加入，另需约 **16.38 GB** 权重，本次查询 revision 为 `b968826d9c46dd6066d109eabc6255188de91218`，不能漏算这笔存储和下载量。
3. 下载、轻量运行器及具体单题输入准备好后，再申请最小 GPU 兼容性检查，测量显存、耗时及输出格式；目前不启动 30 题比较，也没有更新出可靠的新总耗时预算。
4. 若开展 Sonar-TS，对选定的小批题另报 API 调用上限与费用，再执行。全部调用与程序步骤都需保留轨迹，以便区分搜索遗漏、关系核验和最终回答错误。

这份清单用于减少无效复现工作。选择现成模型不等于已经验证研究假设；单凭这几个回答模型的失败，也不足以宣称现有证据集合方法存在共同缺陷。

本次 Git 提交仅新增本报告，不修改 README、模型环境、实验数据、旧脚本或历史结果。
