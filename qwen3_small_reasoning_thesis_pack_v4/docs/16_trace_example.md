# 16. 示例 Trace（论文展示用模板）

> 这是一份“格式模板”。真正的 trace 由 run_agent.py 在 save_trace=true 时输出。

## Sample: mlb_xxxx（multi_doc_qa）

### Step 0: initial retrieval
- query: 原始 question
- hits:
  - d1_c03: (摘要...) 
  - d2_c11: (摘要...)

### Step 1: model output
- output: <search>关键实体 + 关系</search>
- keyword: 关键实体 + 关系
- retrieval hit:
  - d2_c07: (摘要...)
- facts written:
  - fact_001: relation, "A depends on B", evidence d2_c07, conf 0.78
- prune:
  - dropped: [d1_c03]
  - kept: [d2_c11, d2_c07]

### Step 2: model output
- output: <final>最终答案</final>

### Final
- pred: ...
- gold: ...
- n_steps: 2
- n_retrieval: 1
- p95 latency: ...
- gpu peak: ...
