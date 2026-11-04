# Q-Sample 第一版（v1）

已实现并运行 `密度预测 → 逆 CDF → 浮点坐标 → 原始信号插值 → 答案 BCE`，仅用答案标签训练。三个随机种子的合成实验中，自适应采样平均准确率 **97.66%**，均匀采样 **60.94%**。这支持最小机制可训练，**尚未证明查询选择、真实微弱事件或 LLM QA 能力**。

实现与结果说明见 [REPORT.md](REPORT.md)，数值汇总见 [results/aggregate.json](results/aggregate.json)。

## 文件

- `model.py`：五类局部统计、Query FiLM 融合、密度下限、全长密度插值、FP64 CDF、逆变换及一维插值。另提供连续时间 Fourier 特征和投影层。
- `train_synthetic.py`：在线合成数据、答案训练、均匀/无平滑/仅均值/查询盲采样器对照、Query 切换与信号置零诊断。
- `test_model.py`：有限差分梯度检查、极端密度、端点、FFT 平滑与直接卷积对照、端到端梯度、平坦信号和信息旁路控制，共 8 项测试。
- `summarize.py`：汇总本轮 seed 7、11、23 的最终 checkpoint 结果。

依赖 Python 3.10+、PyTorch、Matplotlib。本机验证环境为 PyTorch 2.6.0+cu124、RTX 4090 D；未安装额外包。

## 运行

在本目录执行：

```bash
OMP_NUM_THREADS=4 python -m unittest -v test_model.py
python train_synthetic.py --seed 7 --runs adaptive uniform adaptive_no_blur adaptive_mean_only --output results/signal-seed7
python train_synthetic.py --seed 7 --runs adaptive_query_blind --output results/queryblind-seed7
python train_synthetic.py --seed 11 --runs adaptive uniform adaptive_no_blur adaptive_mean_only adaptive_query_blind --output results/signal-seed11
python train_synthetic.py --seed 23 --runs adaptive uniform adaptive_no_blur adaptive_mean_only adaptive_query_blind --output results/signal-seed23
python summarize.py
```

输出包含配置、逐步 loss/密度梯度、初末密度/采样坐标、指标、PNG 和本地权重。已有输出会覆盖，复跑时建议使用新的 `--output` 目录。CUDA 计算未强制确定性，复跑数值可能略有变化。

默认 `--readout signal`，让第一阶段的答案头只读采样信号，排除直接从坐标读取答案的路径。完整时间投影可用 `--readout signal_time`；另提供 `signal_time_detached` 切断时间输入对坐标的直接梯度，但它仍不能自动排除推理阶段的信息旁路。

可重现已发现的时间坐标捷径：

```bash
python train_synthetic.py --readout signal_time --runs adaptive --output results/time-shortcut-seed7
```

## 接入后续 QA 的边界

`QSample.forward` 返回 `values [B,N,C]`、归一化 `grid [B,N]` 和密度。`TimeProjection` 可将值、坐标、相邻间隔和 Fourier 时间特征映射为连续 Token。它不是修改 LLM 注意力的 RoPE；接入 LLM 时应按后端原有的位置编码方式处理。

本实验 Query 只是正/负极性标量，答案头是小型 MLP，没有自然语言编码器或 LLM。跨记录回答持续时间时，还须提供起始时间、采样率和真实时间跨度，归一化坐标本身不足以恢复物理时间。

完整密度及 CDF 的时间/内存仍为 O(BL)，固定 Token 数只限制后端输入。百万点已验证一次前后向，不能据此声称百万长度训练或 QA 已收敛。

本版本的代码、报告和结果均位于 `v1/`；所有命令在本目录执行。第二版独立位于 [../v2/](../v2/README.md)，不与本版本共享可变代码。
