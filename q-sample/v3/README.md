# Q-Sample 第三版（v3）：NLQTSBench 可行性审计

本版本仅审计官方数据与适配路线，不训练模型、不改写官方数据。

完整结论见 [REPORT_NLQTS_DATA_AUDIT.md](REPORT_NLQTS_DATA_AUDIT.md)：官方区间标签可监督位置，但不是完整证据或唯一正确密度；同输入多 Query 的条件选择收益和无坐标捷径的轻量读出器仍需验证，暂不进入训练。

- [audit_results.json](audit_results.json)：计数、重叠、实际长度、配对诊断、已接触测试样本及划分建议。
- [provenance.json](provenance.json)：版本、来源和环境。
- [acquisition.json](acquisition.json)、[获取历史](acquisition_history.json)：固定抽样和内容复用记录。
- `sources/`：官方元数据快照，保留原始自然语言与答案。
- `audit_data.py`：只读复算；`acquire_audit_sources.py`：缺失来源补齐，按内容指纹复用。

本机复现（不下载、不训练）：

```bash
OMP_NUM_THREADS=4 /root/v016-sonarts-env/bin/python audit_data.py
```

其他机器使用 Python、NumPy、Pandas、Requests，并指定 `--workspace` 与 `--vendor`。未取得的原始 CSV 留为未核验项，不根据文件大小猜测长度。
