# 04 Writing Checklist

## 开写前检查

- 已确认正文主张不是“三任务全面平衡提升”
- 已确认标题级亮点是 `code_qa`，但正式主证据仍为 `canonical`
- 已确认主结果数字来自 `evidence/results_master_table.md`
- 已确认单任务解释来自 `evidence/task_breakdown.md`
- 已确认局限性页会明确写 `single_doc` 回撤与 `3-seed` 未完成

## 写摘要时检查

- 是否明确写出 `4B`、长文档、预算约束、任务路由协议
- 是否写出 `overall` 与 `code_qa` 的正向收益
- 是否避免“全面提升”“普遍更优”“完全替代大模型”这类表述
- 是否在摘要里压住对未完成补充实验的暗示

## 写方法时检查

- 是否突出“任务异质性”而不是“通用 agent”
- 是否写清协议组件服务于什么任务
- 是否解释为什么统一单轮流程不够
- 是否避免把所有工程模块都写成创新点

## 写实验时检查

- 主表是否只使用当前 verified canonical 正式结果
- 是否单独解释 `single_doc` 回撤
- 是否把 `code_qa` 写成亮点任务，而不是唯一身份
- 是否把 monitor 数据从主结论中剥离

## 写局限性时检查

- 是否明确写出 `single_doc_qa` 回撤
- 是否明确写出 `OOM=3`
- 是否明确写出当前缺少 `3-seed confirm`
- 是否明确写出 `code_qa` 来源仍偏 `lcc + repobench-p`

## 定稿前检查

- `claim_to_evidence_matrix` 中每个正文 claim 都能对上
- 没有直接从旧初稿复制冲突口径
- 没有把 partial eval 当正式结果
- 没有把未完成的对照或消融写成既成事实
- 所有表格数字都能回溯到 `report/` 原始文件

