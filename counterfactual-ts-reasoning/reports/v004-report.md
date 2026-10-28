# v004：总仓库目录整理与英文文献引用规范

日期：2026-10-28。本次是归档结构和报告引用格式调整，没有新增实验。

## 仓库用于多个研究方向

`TSQA_ideas` 是多个研究方向的总仓库。此前放在仓库顶层的当前项目文件，现整体归入 `counterfactual-ts-reasoning/`：

```text
TSQA_ideas/
├── .gitignore
└── counterfactual-ts-reasoning/
    ├── .gitignore
    ├── .vscode/
    ├── BACKUP.md
    ├── README.md
    ├── data/
    ├── pyproject.toml
    ├── pyrightconfig.json
    ├── reports/
    ├── scripts/
    ├── src/
    └── tests/
```

未来其他方向可作为同级目录加入，不需要混入本项目。项目 README 仅移动位置，内容不改。顶层保留原 `.gitignore`，项目内另保存同内容副本。

## 英文原文保持原样

论文标题保留完整英文原名，作者姓氏保留英文，不用中文译名替代。中文用于解释论文内容和本项目判断；引用的英文句子、提示词和模型原始回复不翻译、不改写。

v003 原始 Markdown 中的论文标题已经是英文；截图中的中文标题可能来自浏览器翻译。本次进一步统一英文作者写法，补齐完整标题，并将标题设为行内代码格式。若页面仍被自动翻译，应切换浏览器的“显示原文”。

最新研究综合报告：[v003-report.md](v003-report.md)。历史报告及其相对链接随项目一起移动。

## 服务器目录与后续提交

- 总仓库工作副本：`/root/autodl-tmp/cf-run/TSQA_ideas/`。
- 原实验工作目录：`/root/autodl-tmp/cf-run/counterfactual-ts-reasoning/`，保留不动。
- 原模型与 `realtime-tslm` 依赖位置保持原状；不从本次归档副本重新运行实验。
- 本次迁移已有 Git 归档内容，未额外上传原实验目录中尚未纳入 Git 的输入、回复或脚本。
- 后续本方向的版本报告放入总仓库的 `counterfactual-ts-reasoning/reports/`。通常每次只提交新版本报告；本次按明确要求完成目录重组和引用格式调整。

本次没有训练、GPU 推理、重新生成数据或覆盖实验结果。
