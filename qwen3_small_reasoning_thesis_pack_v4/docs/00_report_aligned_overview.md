# 00. 总览（与“可行性深度研究报告”对齐）

## 核心问题
在 RTX 4060 8GB 下，长文档任务面临两类瓶颈：
- 上下文窗口不足（无法一次塞入所有证据）
- 显存不足（模型 + KV cache 容量受限）

## 核心方案
Edge-Reasoning Agent = Qwen3-8B-Thinking + 迭代式元认知检索 + Thinking-Aware Eviction（工作记忆式淘汰） + （可选）神经符号一致性检查

## 必须交付的 3 个实验结果（论文第 5 章）
1) 主结果：Agent > Standard RAG（准确率）
2) 成本曲线：Accuracy vs (Latency / Retrieval Count / Tokens)
3) 鲁棒性：显存峰值稳定，OOM=0

## 文档导览（从工程到论文）
- I/O 契约：docs/12_io_contracts.md
- Agent 算法与状态机：docs/03_agent_algorithm.md、docs/18_protocol_state_machine.md
- 指标定义：docs/14_metrics_definition.md
- 成本口径：docs/15_cost_model.md
- 图规范：docs/13_figures_spec.md
- 安全（注入防护）：docs/16_security_prompt_injection.md
- 蒸馏质检：docs/17_distill_data_quality.md
- Student 评测：docs/19_student_controller_eval.md
