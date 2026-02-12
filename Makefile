SHELL := /bin/bash
PYTHON ?= python3

.PHONY: smoke preflight prepare prepare_strict index baseline agent eval distill train_student eval_student ablations bench_key all all_formal all_smoke clean

smoke:
	bash scripts/cmd/smoke.sh

preflight:
	bash scripts/cmd/preflight_formal.sh

prepare:
	$(PYTHON) scripts/prepare_minilongbench.py --out data/minilongbench_{split}.jsonl --split all --mode remote

prepare_strict:
	$(PYTHON) scripts/prepare_minilongbench.py --out data/minilongbench_{split}.jsonl --split all --mode remote --strict_remote

index:
	$(PYTHON) scripts/build_corpus.py --in data/minilongbench_train.jsonl --out data/corpus_chunks.jsonl --index_dir data/index/

baseline:
	$(PYTHON) run_baseline_rag.py --config configs/baseline_rag.yaml --dataset data/minilongbench_test.jsonl --index_dir data/index --out results/baseline_rag.jsonl --run_mode formal --retrieval_scope sample

agent:
	$(PYTHON) run_agent.py --config configs/agent.yaml --dataset data/minilongbench_test.jsonl --index_dir data/index --out results/edge_agent.jsonl --run_mode formal --retrieval_scope sample

eval:
	$(PYTHON) evaluate.py --gold data/minilongbench_test.jsonl --pred results/baseline_rag.jsonl results/edge_agent.jsonl --out_dir report/ --run_mode formal

distill:
	$(PYTHON) scripts/distill_controller_data.py --teacher_config configs/teacher_distill.yaml --dataset data/minilongbench_train.jsonl --out data/student_train.jsonl --run_mode formal

train_student:
	$(PYTHON) train_student.py --config configs/train_qlora.yaml --train data/student_train.jsonl --out_dir checkpoints/student --run_mode formal --prefer_real

eval_student:
	$(PYTHON) scripts/eval_student_controller.py --agent_config configs/agent.yaml --dataset data/minilongbench_test.jsonl --checkpoint checkpoints/student --out_dir report_student/ --run_mode formal

ablations:
	RUN_MODE=formal RETRIEVAL_SCOPE=sample bash scripts/run_ablations.sh data/minilongbench_test.jsonl data/index

bench_key:
	bash scripts/cmd/bench_key_tasks.sh

all_smoke:
	bash scripts/cmd/smoke.sh

all_formal:
	bash scripts/cmd/all.sh

all: all_formal

clean:
	rm -rf results report report_tiny report_student checkpoints data/index data/corpus_chunks.jsonl data/minilongbench_train.jsonl data/minilongbench_valid.jsonl data/minilongbench_test.jsonl data/student_train.jsonl data/student_train_stats.json results/ablations
