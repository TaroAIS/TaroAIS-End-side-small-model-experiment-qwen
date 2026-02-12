# 06. 实验设计与消融

## 主分组
- baseline_rag（一次 Top-K，non-thinking）
- edge_agent（thinking + 迭代检索 + budget/memory）

## 必做消融（>=3）
- think_off
- iterative_off
- memory_sliding
- inj_defense_off（额外，安全消融）

## 通过条件
- make smoke / make all 跑通
- schema 校验通过
- report 生成 CSV + PNG（图规范见 docs/13_figures_spec.md）
