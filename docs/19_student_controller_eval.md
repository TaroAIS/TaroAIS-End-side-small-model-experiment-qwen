# 19. Student-Controller 评测

## 19.1 目标
student 只回答一个问题：
- 冻结后的 `4B edge_agent` 是否可以蒸馏出更轻的控制器，同时尽量保留主趋势。

## 19.2 评测分层
### A. 控制器行为评测
- 指标：
  - `trigger_acc`
  - `macro_f1`
  - `keyword_hit_rate`

### B. 端到端评测
- student 接管检索控制决策
- 主推理模型仍按冻结后的 `Qwen3 4B` 主线配置运行
- 对比维度：
  - F1
  - `avg_retrieval`
  - latency

## 19.3 执行顺序
1. `holdout100`
2. `canonical`

## 19.4 结果汇报要求
- 必报 `teacher / student` 质量差距
- 必报时延或资源收益
- 必报三任务相对排序是否保持一致
- 必须说明 student 不参与主结论通过判定

## 19.5 论文定位
- student 是效率路线补充证据
- student 不进入主结果表，也不替代 canonical 主结论
