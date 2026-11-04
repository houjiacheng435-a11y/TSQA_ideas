# Q-Sample v5

真实 UK-DALE-Haystack 的端到端采样与双任务 QA 实验。v1–v4 保持原样。结果解释与完成状态见 [实现报告](REPORT_MODEL_IMPLEMENTATION.md)。所有命令在本目录执行。

- `model.py`：冻结 BERT-tiny、多尺度 CNN、FiLM 密度、可微逆 CDF、原信号插值、双任务时间 Transformer。
- `data.py` / `source_io.py` / `prepare.py`：固定官方子集、已有缓存复用、官方前值保持重建、输入/监督分离。
- `losses.py`：存在性 BCE；定位 Huber + IoU；三类可切换代理密度 KL；可选低熵塌缩正则。
- `train.py` / `experiment.py`：三种监督条件、四种采样方法、独立训练读出器、3 个固定种子。
- `evaluate.py` / `infer.py`：官方评分与完全不需要标注的原始问题推理。
- `tests.py` / `diagnose.py` / `audit_inputs.py`：梯度、真实输入、独立坐标头及干预、重复/背景风险。

## 环境与缓存

本服务器使用 Python 3.12、PyTorch 2.6.0+cu124、Transformers 4.52.4、NumPy 1.26.4、PyArrow 19.0.1、Matplotlib 3.9.2；完整版本见 `results/environment.json`。无需安装 LLM 或调用 API。

```bash
export PYTHONPATH=/root/v020-extra
PY=/root/v016-sonarts-env/bin/python
# 其他服务器可修改公开缓存路径，不能更换固定数据 revision。
export UKDALE_CACHE=/root/autodl-tmp/cf-run/data/qsample-v4-ukdale/eb86b2ecc46b2f26b3a4e1768d7b479dc9abc521
export TS_HAYSTACK_SOURCE=/root/autodl-tmp/cf-run/vendor/v020/TS-Haystack
```

官方代码应检出 `5e8d3162d47176e19fbd9c5f3d3cf9c6e0e9a7d4`。复用 v4 已有元数据和范围缓存；不会下载完整的 1.758 GB 信号库。`UKDALE_CACHE` 内需要官方任务 parquet 和 bout index；全新机器可使用本版 `prepare.py --metadata`，仅补齐两任务的30个QA分片和bout index，全部校验后复用；v5不依赖v4代码或目录内文件。模型文本权重另占约 18 MB，固定 revision 与校验值记录于 `text_model_blobs.json` 和 `results/text_acquisition.json`。

```bash
$PY prepare.py --metadata --text --groups smoke overfit train validation robust_validation
$PY data.py
$PY -m unittest tests -v
$PY train.py --overfit
$PY experiment.py --seed 7
$PY experiment.py --seed 11
$PY experiment.py --seed 23
$PY experiment.py --controls
# 仅在模型/配置冻结后取得测试信号并正式评测。
$PY prepare.py --groups test robust_test
$PY experiment.py --all --test
$PY experiment.py --controls --test
$PY finalize_evaluations.py --diagnostics --plots
$PY diagnose.py results/adaptive_joint_s7/final.pt --group test
$PY audit_inputs.py
```

`execute_stages.py` 可按测试→32题过拟合→主矩阵自动顺序执行；它不启动长序列或测试评测。配置冲突会报错；已完成的 final checkpoint 会跳过，不静默覆盖。长序列命令是单独的 `experiment.py --long`，执行状态以报告为准。所有主模型使用原始信号，不使用高斯平滑。训练仅读取 Train 的监督标签；离线缓存验证/测试原始 Query 的固定编码不更新任何参数。

## 无标注推理

```bash
$PY infer.py results/adaptive_joint_s7/final.pt /path/to/raw_power.npy \
  'Detect whether the kettle ran in this trace.' --task existence --dt 6
```

输入为原生单通道功率（W）、官方原始自然语言问题和公开任务类型/采样周期。定位输出官方窗口相对 `HH:MM:SS - HH:MM:SS`。此入口不加载官方 QA 样本、不接收 needles、difficulty 或答案。数值上 `T=L×dt`，最后观测位置为 `(L−1)×dt`，两者不可混淆。

所有方法使用相同的时间特征：窗口相对位置、间隔、实际时长。`signal`、`gaps`、`absolute` 为可切换消融；`absolute` 表示窗口相对时间，绝不表示 UTC。独立 Coordinate-only 与 Query-only 需要重新训练，不能用一次置零干预代替。测试输出包含逐题答案；小样本结果不是完整 benchmark 排名。

`execute_controls.py` 在24个主运行结束后执行独立控制及额外的预热保持性复跑，再对全部固定样本正式评分；复跑不替换主矩阵。`execute_long.py` 只在主实验评分完成后运行原生14400点、五预算的小规模试验。下载过程中部分连接可能重置，重新运行相同 `prepare.py --groups ... --workers 4` 补齐原清单；不得换题。主矩阵需要约10分钟GPU计算，下载时长取决于网络。

如需尽量减少 CUDA 数值变化，可在进程启动前设置 `CUBLAS_WORKSPACE_CONFIG=:4096:8`。记录了所有种子与配置，但 CUDA 插值、池化和 FlashAttention 反向仍可能不具备逐bit确定性；跨种子结果应按统计波动解释。

完成的checkpoint都保留在服务器 `results/*/final.pt`；固定seed7参考模型还保留在 `models/`。依照仓库现有 `.gitignore`，权重不上传Git；[CHECKPOINTS.json](CHECKPOINTS.json)记录两个参考权重的大小和SHA-256。GitHub上提供代码、完整配置、逐题结果和图，运行上述固定训练即可重新生成权重。

长序列已实际完成的小规模复现：

```bash
$PY prepare.py --groups long_train long_validation long_test --workers 4
$PY experiment.py --long
$PY experiment.py --long --test
$PY summarize.py
$PY analyze_results.py
```

报告中所有20个长试验是单种子、每任务仅4道Test题，不能用于稳健排名。
