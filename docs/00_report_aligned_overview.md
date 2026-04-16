# 00. 总览

## 核心问题
在端侧资源受限条件下，小模型很难同时满足：
- 长文档问答质量
- 时延
- 稳定性

## 当前方案
Edge-Reasoning Agent =
- `Qwen3 4B`
- 协议化迭代检索
- fact memory
- early-stop
- task-aware budget

## 当前必须交付的论文证据
1. canonical 主结果表
2. 预算匹配与单轮强基线对照
3. 消融表
4. 3-seed confirm
5. student 附加实验
