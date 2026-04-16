# 毕业论文复用骨架（中文）

本骨架建立在会议稿主线之上，但扩展系统设计、实现细节、实验流程和工程保障。

## 建议总结构

1. 绪论
2. 相关研究
3. 系统设计与问题定义
4. 任务路由式长文档协议
5. 数据体系与实验设置
6. 主结果与机制分析
7. 工程实现与运行保障
8. 局限性与未来工作
9. 结论

## 第 1 章 绪论

### 要写什么

- 研究背景：小模型、长文档、预算约束
- 研究动机：统一流程对异质任务不够
- 研究目标：不是追求“全面碾压”，而是追求“在有限预算下实现更好的任务分配与整体收益”

### 可直接复用会议稿

- 问题定义
- 贡献概述
- 正式结果摘要

## 第 2 章 相关研究

在会议稿相关工作基础上扩展：

- 长文档评测基准
- 端侧/小模型推理
- RAG 与多步协议
- 代码理解与仓库问答

## 第 3 章 系统设计与问题定义

### 需要补的内容

- 系统目标与非目标
- `4B + canonical` 主线的原因
- 任务分组与协议设计的对应关系
- 运行时约束：时延、显存、OOM、恢复机制

### 可参考旧文档

- `docs/02_system_architecture.md`
- `docs/18_protocol_state_machine.md`
- `docs/36_runtime_guard_and_resume.md`

## 第 4 章 任务路由式长文档协议

### 小节建议

1. 协议输入输出
2. 初始任务感知
3. 检索晋级与预算守卫
4. 迭代检索与事实记忆
5. 提前停止与回退逻辑
6. 对不同任务的差异化影响

### 本章写作重点

- 解释“为什么这样设计”
- 不要把所有工程细节都当成创新点
- 明确 `code_qa` 为何是受益最大的任务

## 第 5 章 数据体系与实验设置

### 需要写清

- `LongBench_3tasks canonical` 作为唯一主结论
- `single_doc_qa=750, multi_doc_qa=800, code_qa=1000`
- 当前正式结论基于单 seed
- monitor 集和附录集只用于过程性或补充性说明

### 表格建议

- 数据集总表
- 指标定义表
- 方法与对照组说明表

## 第 6 章 主结果与机制分析

这一章是毕业稿的核心，也可以直接从会议稿结果章扩展。

### 6.1 主结果

直接引用：

- [../evidence/results_master_table.md](../evidence/results_master_table.md)

### 6.2 单任务分解

直接引用：

- [../evidence/task_breakdown.md](../evidence/task_breakdown.md)

### 6.3 案例分析

直接引用：

- [../evidence/error_case_digest.md](../evidence/error_case_digest.md)

### 6.4 收益与代价

重点解释：

- overall 为什么提升
- code_qa 为什么大幅提升
- single_doc 为什么回撤
- 时延和 OOM 的代价如何理解

## 第 7 章 工程实现与运行保障

这是毕业稿比会议稿更需要展开的部分。

### 需要覆盖

- sharded canonical 运行机制
- stall 检测与恢复
- sample-level timeout
- formal evaluate 卡住后的修复
- 为什么实验口径需要 source-of-truth 治理

### 可参考材料

- `docs/41_paper_canonical_execution_log_2026-04-16.md`
- `docs/39_paper_canonical_live_status.md`

## 第 8 章 局限性与未来工作

不能回避：

- `single_doc_qa` 回撤
- `3-seed` 未完成
- 更强控制基线尚未形成正式结果
- `code_qa` 外部效度仍有边界

## 第 9 章 结论

建议落点：

- 小模型长文档协议的价值
- `code_qa` 亮点与 canonical 主证据如何兼容
- 未来应继续围绕任务异质性和 single-doc 协议修复推进

