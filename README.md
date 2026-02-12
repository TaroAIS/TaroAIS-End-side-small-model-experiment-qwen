# Qwen3 端侧推理 + 小模型蒸馏 毕设实验规范包（v4，给 Codex）

生成日期：2026-02-12

> v4 = v3 + 全量增强：**JSON Schema、I/O 契约、状态机、Makefile/脚本、BibTeX、图规范、示例 Trace、指标/成本口径、注入防护、蒸馏质检、Student 专用评测、环境锁定、run metadata**。

---

## 快速开始（给你 / 给 Codex）
1) 把 `codex/codex_prompt.md` 复制给 Codex，让它在新仓库生成完整代码。
2) 先跑 smoke test（<= 5 分钟，允许 mock/fallback）：
   - `bash scripts/cmd/smoke.sh`
3) 再跑 formal 主实验（严格模式，禁止 mock）：
   - `bash scripts/cmd/all.sh`

### 命令脚本入口（推荐）
- 目录：`scripts/cmd/`
- 文档：`scripts/cmd/README.md`
- 常用：
  - `bash scripts/cmd/preflight_formal.sh`
  - `bash scripts/cmd/prepare_remote_strict.sh`
  - `bash scripts/cmd/smoke.sh`
  - `bash scripts/cmd/all.sh`

---

## 数据来源与版本（Smoke vs 正式实验）

### 1) Smoke 数据集（随包附带）
- 文件：`smoke_data/minilongbench_tiny.jsonl`
- 内容：3 条样本（`single_doc_qa` / `multi_doc_qa` / `code_qa` 各 1 条）
- 目的：让 `baseline -> agent -> evaluate` 在 5 分钟内跑通，先验证 I/O、schema、报告产物链路。

### 2) 正式实验数据集（论文主实验）
- 数据源：Hugging Face `linggm/MiniLongBench`
- 上游项目：`https://github.com/MilkThink-Lab/MiniLongBench`
- 默认版本（脚本内已固定）：`0ba7bf46265f1f783653693fb6b581f617f37275`
  - 该值是 HF 数据集仓库 revision（commit sha），用于保证可复现。

> 说明：`scripts/prepare_minilongbench.py` 会从官方 `data/*.jsonl` 读取任务样本，转换到本项目 schema（`id/task/question/documents/answer`），并按固定随机种子切分出 `train/valid/test`。

### 3) 生成命令
- 正式数据（严格远程，下载失败就报错）：
  - `python scripts/prepare_minilongbench.py --mode remote --split all --strict_remote`
- 正式数据（默认模式，远程失败自动回退到 smoke 扩展）：
  - `python scripts/prepare_minilongbench.py --mode remote --split all`
- 离线模式（仅 smoke 扩展）：
  - `python scripts/prepare_minilongbench.py --mode offline --split all`

### 4) 输出与追溯
- 约定输出：`data/minilongbench_{split}.jsonl`
- 数据来源元信息：`data/minilongbench_source.json`
  - 记录 source、revision、任务文件列表、样本数、回退原因（若有）

---

## 目录说明
- `docs/`：研究 + 工程规范（核心）
- `configs/`：所有超参 YAML
- `schemas/`：JSON Schema（数据/结果/facts/run 元信息）
- `templates/`：论文表格模板 + 实验记录模板 + metadata 模板
- `smoke_data/`：3 条样例，保证 pipeline 可跑通
- `scripts/`：一键 smoke + 辅助脚本（不依赖你代码实现，但给 Codex 明确目标）
- `codex/`：给 Codex 的总 Prompt + 验收测试清单
- `conda.yaml`、`Dockerfile`：环境锁定（可选）

---

## 你最终需要在仓库里跑通（Definition of Done）
- `make smoke`（smoke 链路，允许 fallback）
- `make all`（formal 链路：`run_mode=formal` + `retrieval_scope=sample`）
- 输出：`results/*.jsonl`、`report/*.csv`、`report/*.png`
- 运行稳定：OOM=0；输出文件满足 `schemas/*.json` 校验
- formal 结果要求：`backend_mode=real`（不接受 mock）
