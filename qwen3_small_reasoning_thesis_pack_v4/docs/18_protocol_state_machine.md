# 18. 协议状态机（实现细节，Codex 必须照抄）

## 状态
- PARSE：从 LLM 输出解析 tag
- OK_SEARCH：解析到 <search>
- OK_FINAL：解析到 <final>
- REPAIR：发送纠错 prompt（最多 1 次）
- FALLBACK_FINAL：兜底 final（并记录 error_count++）

## 伪代码
state = PARSE
retries = 0
while True:
  tag = parse(output)
  if tag in {SEARCH, FINAL}: goto OK_*
  if retries < 1:
     retries += 1
     output = llm(repair_prompt(output))
     continue
  else:
     output = force_final(output)
     error_count += 1
     goto OK_FINAL
