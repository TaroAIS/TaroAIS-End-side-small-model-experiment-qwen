# 17. 蒸馏数据质检规范（Teacher -> Student-Controller）

> 目的：保证 Student 训练数据“格式严格、语义可用”，否则小模型学坏。

## 17.1 合法输出定义
- 必须严格命中 `<search>...</search>` 或 `<final>...</final>`
- search keyword 长度在 [min_keyword_len, max_keyword_len]
- 不允许输出额外文本（strict_tags）

## 17.2 修复策略
- 若不合法：允许用“格式纠错 prompt”重试一次（allow_repair_once）
- 仍不合法：丢弃样本（drop_if_still_invalid=true）
- 记录：
  - invalid_rate（初次不合法比例）
  - repaired_rate（修复成功比例）
  - dropped_rate（最终丢弃比例）

## 17.3 数据平衡（建议）
- 控制 search vs final 比例（避免模型总是 search 或总是 final）
- 可对困难样本增加采样权重（例如 multi_doc_qa）

## 17.4 产物
distill 脚本输出：
- data/student_train.jsonl（messages + output）
- data/student_train_stats.json（上述比例统计）
