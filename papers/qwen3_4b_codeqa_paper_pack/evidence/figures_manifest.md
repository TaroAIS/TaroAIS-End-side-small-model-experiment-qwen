# Figures Manifest

本页统一登记当前正式报告下可直接复用的图。

来源目录：

- 包内图表原件：`assets/figures/`
- 上游生成位置：`report/formal_paper_canonical_s42_current/`

## 图表清单

| 图文件 | 建议图号 | 含义 | 推荐放置 | 配套结论 |
| --- | --- | --- | --- | --- |
| `accuracy_bar.png` | Figure 1 | baseline 与 edge_agent 的 overall F1 对比 | 正文主结果区 | 证明 overall 提升 |
| `cost_effect_curve.png` | Figure 2 | `p95 latency` 与 F1 的精度-成本关系 | 正文结果分析区 | 说明收益伴随时延代价 |
| `retrieval_effect_curve.png` | Figure 3 | `avg_retrieval` 与 F1 的关系 | 正文或附录 | 说明协议通过更高检索预算换取收益 |
| `gpu_mem_curve.png` | Figure 4 | peak/mean GPU 显存对比 | 附录优先 | 说明成本不只来自时延，还来自资源占用 |

## 推荐 caption 草案

### Figure 1

> Comparison of overall F1 on the verified canonical single-seed run. The task-routed protocol substantially improves the overall score over the standard RAG baseline.

### Figure 2

> Accuracy-cost trade-off between the baseline and the agent protocol. The gain in F1 is accompanied by a higher tail latency.

### Figure 3

> Retrieval intensity versus accuracy. The agent benefits from a larger average retrieval budget than the one-shot baseline.

### Figure 4

> Peak and mean GPU memory usage of the compared methods on the verified canonical run.

## 使用建议

### 正文必须保留

- `accuracy_bar.png`
- `cost_effect_curve.png`

### 正文可选

- `retrieval_effect_curve.png`

### 附录优先

- `gpu_mem_curve.png`

## 包内图表原件位置

为便于打包和直接插图，当前包内已经复制了一份图表原件：

- `assets/figures/accuracy_bar.png`
- `assets/figures/cost_effect_curve.png`
- `assets/figures/retrieval_effect_curve.png`
- `assets/figures/gpu_mem_curve.png`

写稿时优先从这里取图即可。

## 不要怎么用

- 不要把这些图解释成“所有任务都变好”
- 不要只展示 Figure 1 而不报告 Figure 2 的代价信息
- 不要把 GPU 图写成算法创新，而是写成运行边界
