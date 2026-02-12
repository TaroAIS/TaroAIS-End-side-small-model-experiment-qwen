# 14. 指标定义（严谨口径，避免答辩被问倒）

## 14.1 EM（Exact Match）
- normalize（可开关）：去除空白、常见标点、大小写（英）
- 中文建议：按字符级 normalize（或可选 jieba 分词，但需声明）

EM = 1 if normalized(pred) == normalized(gold) else 0

## 14.2 Token-level F1
- 将 normalized 字符/Token 列表化
- precision = overlap / len(pred_tokens)
- recall = overlap / len(gold_tokens)
- F1 = 2PR/(P+R)

## 14.3 多答案
若 gold 为列表：取 max F1/EM（对齐常见 QA 评测口径）

## 14.4 统计口径
- avg_*：对样本求均值
- P50/P95 latency：对样本的 total latency 求分位数
- OOM：统计运行中异常/返回码，必须为 0（主实验）
