# 13. 图表规范（论文可直接用）

> evaluate.py 必须按这些固定文件名输出，避免你后期整理地狱。

## 13.1 accuracy_bar.png
- x：method（baseline_rag, edge_agent, ablations...）
- y：EM 或 F1（默认 F1）
- 标注：数值（保留 2 位小数）

## 13.2 cost_effect_curve.png
- x：P95 latency (ms)
- y：F1
- 点：每个方法 1 个点（或多点：不同 max_steps）
- 备注：显示 Pareto 前沿（可选）

## 13.3 retrieval_effect_curve.png
- x：avg_retrieval
- y：F1
- 目的：证明“更多检索”在一定范围内带来收益

## 13.4 gpu_mem_curve.png（可选）
- x：time (sample index or seconds)
- y：GPU memory (MB)
- 使用：展示 OOM 规避与稳定性（可选）
