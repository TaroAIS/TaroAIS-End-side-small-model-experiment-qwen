# 38. code_qa 外部效度补充

## 38.1 为什么需要这份附录
当前 canonical 中的 `code_qa` 样本数并不少，但来源主要是 `lcc + repobench-p`。这足以支持“代码长上下文是重要亮点任务”，但还不足以把整篇论文写成纯代码智能论文。因此需要一份补充附录，回答两个问题：

1. 主方法在 `code_qa` 上的收益，是否能扩展到不同语言来源。
2. 当前 `code_qa` 亮点是否只是某一个狭窄来源的偶然现象。

## 38.2 补充集构造
- 来源：
  - `data/train_ext/code_qa/repobench_python_valid.jsonl`
  - `data/train_ext/code_qa/repobench_java_valid.jsonl`
- 采样策略：
  - 每个来源固定抽样 `50` 条
  - 默认 `seed = 42`
- 输出：
  - `data/main_eval/code_generalization/repobench_python_appendix.jsonl`
  - `data/main_eval/code_generalization/repobench_java_appendix.jsonl`
  - `data/main_eval/code_generalization/code_generalization_appendix.jsonl`

## 38.3 执行入口
- 数据构造：
  - `python scripts/build_code_generalization_subset.py`
- 一键附录评测：
  - `bash scripts/cmd/code_generalization_appendix.sh`

## 38.4 结果使用规则
- 这份补充集只用于 `code_qa` 外部效度说明
- 不替代 canonical 主结论
- 不用于重定义主门槛
- 推荐写作位置：
  - 正文的补充实验小节
  - 或附录的外部效度小节

## 38.5 建议写法
- 若附录结果继续优于 baseline，可写：
  - `edge_agent_4b` 在 RepoBench Python / Java 补充集上仍保持正向收益，说明 `code_qa` 亮点不完全依赖 canonical 中的单一来源。
- 若附录结果波动较大，可写：
  - `code_qa` 的亮点收益在不同语言与仓库分布上存在差异，因此本文仍将其定位为高价值亮点任务，而非唯一主结论。
