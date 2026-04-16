# 32. Round 6 Trigger Plan

## Purpose

This note defines what to do immediately after the first canonical single-seed report is available for the current promoted winner `configs/agent_qwen3_4b_fast.yaml`.

## Freeze Condition

Freeze the fast line and move on to controls / ablations when all of the following hold on canonical single-seed:

- overall F1 `>= 0.34`
- single_doc F1 `>= 0.29`
- p95 ratio `<= 1.8`
- no obvious catastrophic regression in `code_qa` or `multi_doc_qa`

## If Canonical Misses The Gate

Only one factor may change in Round 6.

### Case A: `multi_doc_qa` is the main deficit

Use a `multi_doc_only_lift` candidate if:

- overall is below target, and
- `multi_doc_qa` is clearly the lowest or flattest-improving task, and
- `single_doc_qa` and latency are still acceptable

Hypothesis:

- current 4B fast already beats baseline on `code_qa` and `single_doc_qa`
- the weakest gain is `multi_doc_qa`
- Round 6 should first try a surgical multi-doc retrieval lift instead of a global recall expansion

### Case B: `code_qa` is the main deficit

Use a `code_only_lift` candidate if:

- canonical `code_qa` stays below the paper-ready target, and
- `single_doc_qa` remains healthy, and
- latency still has some room

Hypothesis:

- current fast line is already close to the desired code target
- a small code-only retrieval / decode lift may close the last gap without damaging other tasks

### Case C: latency fails before quality fails

Keep the fast line frozen and do not increase retrieval or decoding budgets further.

Hypothesis:

- if canonical quality is close but p95 is already over the threshold, heavier candidates will weaken the paper story
- in that case the best move is to preserve the current fast line and frame the result as a budget-aware balance point

## Candidate Ordering

1. `multi_doc_only_lift`
2. `code_only_lift`
3. no further lift, freeze current fast

## Why this ordering

- Holdout evidence shows the current fast line already has a meaningful gain over baseline on `code_qa`.
- The smallest gain vs baseline is on `multi_doc_qa`, so that is the first place to probe if canonical still misses the gate.
- Historical heavier candidates improved quality locally but damaged latency too much, so Round 6 must remain surgical.
