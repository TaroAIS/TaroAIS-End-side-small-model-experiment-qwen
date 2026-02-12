# 03. Edge-Reasoning Agent 算法与协议（硬契约）

## 3.1 协议：只允许两种输出
- `<search>关键词</search>`
- `<final>答案</final>`

## 3.2 状态机（实现见 docs/18_protocol_state_machine.md）
- PARSE -> (OK) -> CONTINUE/STOP
- PARSE -> (FAIL) -> REPAIR_ONCE -> PARSE
- PARSE -> (FAIL again) -> FALLBACK_FINAL

## 3.3 迭代检索与预算控制
- 初始检索 Top-K_init
- 每轮 <search> 追加 Top-K_iter
- 每轮都必须执行预算检查：
  - prompt tokens > max_prompt_tokens => prune
  - prune 策略：sliding_window 或 fact_memory

## 3.4 Memory 策略（用于消融）
A) sliding_window：丢最早 chunks
B) fact_memory（主推）：抽取 facts 写入 memory_store；prune 时保留支撑高相关/高新颖 facts 的证据 chunks

## 3.5 Prompt Injection 防护
检索到的 chunks 必须按“证据引用”方式加入 prompt：
- 可选剥离注入片段（patterns）
- quote + label evidence（详见 docs/16_security_prompt_injection.md）

## 3.6 输出 JSON schema
结果 JSONL 必须符合 schemas/result.schema.json
