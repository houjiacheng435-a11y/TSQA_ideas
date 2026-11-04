# Q-Sample 第四版：UK-DALE-Haystack 审计

结论 **B：可用于机制验证，条件采样必要性尚未成立**。详见 [REPORT_UKDALE_DATA_AUDIT.md](REPORT_UKDALE_DATA_AUDIT.md)。本版只做 CPU 数据审计、固定 12 条训练题的真实信号重建与波形代理诊断，没有训练采样模型。

数据固定为 HF `nz00shuuuu/uk-dale-haystack@eb86b2ecc46b2f26b3a4e1768d7b479dc9abc521`，官方源码为 `AI-X-Labs/TS-Haystack@5e8d3162d47176e19fbd9c5f3d3cf9c6e0e9a7d4`。复用了服务器已有代码和环境。`sources/` 是公开官方说明和轻量元数据快照；没有完整波形、模型权重或原始 HDF5。

逐表转换清单的完整缺测区间较大，留在仓库外缓存；仓库内 `sources/signals/conversion_manifest_summary.json` 保留逐表统计、固定下载链接和原文件 SHA256，不把数十万行缺测清单混入代码审查。

在本目录运行。当前服务器的解释器为 `/root/v016-sonarts-env/bin/python`，已有 PyArrow 位于 `/root/v020-extra`：

```bash
export PYTHONPATH=/root/v020-extra
export TS_HAYSTACK_SOURCE=/root/autodl-tmp/cf-run/vendor/v020/TS-Haystack
/root/v016-sonarts-env/bin/python acquire_metadata.py
/root/v016-sonarts-env/bin/python audit_metadata.py
/root/v016-sonarts-env/bin/python audit_source_isolation.py
/root/v016-sonarts-env/bin/python check_semantics.py
/root/v016-sonarts-env/bin/python -m unittest -v test_audit.py
/root/v016-sonarts-env/bin/python signal_diagnostic.py
/root/v016-sonarts-env/bin/python oracle_fidelity.py
```

其他机器需要 Python 3.12、NumPy 1.26.4、Pandas 2.2.3、PyArrow 19.0.1、Requests 2.31.0、Matplotlib 3.9.2，并自行将固定官方代码路径传给 `TS_HAYSTACK_SOURCE`；不需要 CUDA、LLM 或 PyTorch。数据缓存默认在仓库同级的 `data/qsample-v4-ukdale/<revision>/`，首次只获取全部 QA 文本配方和 bout index（约 14.9 MB），信号通过校验过的 HTTP Range 按窗口读取。已有文件复用并核验；不要清除缓存再重复下载。远端若不支持 Range，脚本会失败，不会退回整库下载。

脚本职责：

- `audit_metadata.py`：实际数量、答案、输入配方配对、背景重叠及目标 OFF 的完整索引核验。
- `audit_source_isolation.py`：按真实读取窗口与周划分生成只读候选视图，保留源重叠与标签冲突见证，不修改官方行。
- `check_semantics.py`：直接执行固定官方评分逻辑，核验相对时间、训练先验基线、特权端点坐标反例。仅 train 拟合答案频数；Val/Test 用于审计评分。
- `signal_diagnostic.py`：选定 train 行的 NPY 字节读取、官方函数重建与来源记录；失败也写入结果。
- `oracle_fidelity.py`：四种固定采样策略、五种预算，使用同一重建器，不生成或改写官方问题。它是波形保留代理，不能称为 QA 成绩或最优 Oracle 上界。

数据/模型输入边界：`needles_json`、`other_bouts_json`、`difficulty_config_json` 和完整 bout index 在这里仅用于审计及特权诊断；不可作为实际部署推理输入。未来空间训练代理只可由合法训练标签构造。v1–v3 的实现与结果没有被本版覆盖。

元数据审计是确定性的；诊断样本按固定规则选择，不按结果挑选。采样细分的并列候选由 NumPy 首索引规则处理，无随机种子。索引测试使用固定 seed=7。逐项结果、数据 revision、来源哈希和环境见相应 JSON 与报告。
