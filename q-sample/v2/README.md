# Q-Sample 第二版（v2）

本目录独立保存第二阶段代码、测试、报告、结果与本地权重，不导入第一版代码。完整结论见 [REPORT.md](REPORT.md)。69 项主矩阵没有验证稳定、有用的 Query 条件证据选择；另保留粗特征、预算诊断与开发失败运行。

- `model.py`、`phase2_model.py`：独立采样模型与 Signal-Only 答案头。
- `phase2_data.py`：四类别形态任务。
- `phase2_experiment.py`、`run_phase2.py`：单项实验与冻结矩阵。
- `phase2_probe.py`、`phase2_budget_probe.py`：诊断。
- `results/`：主实验、诊断、训练曲线、图表和运行时源码存档。

在本目录执行（Python 3.10+、PyTorch、NumPy、Matplotlib）：

```bash
OMP_NUM_THREADS=4 python -m unittest -v test_model.py test_phase2.py
```

复跑必须使用新目录：

```bash
python run_phase2.py --output results/reproduce/main
python phase2_probe.py --root results/reproduce
python phase2_budget_probe.py --root results/reproduce
python summarize_phase2.py --root results/reproduce
```

本次目录迁移没有重训或修改历史实验指标。原配置及日志中的 `results/phase2/` 对应现 `v2/results/`；原始源码及其哈希保留在 `results/source/`。当前入口只修改默认输出路径。详见 [MIGRATION.json](MIGRATION.json)。
