SHELL := /bin/bash
PYTHON ?= python3

.PHONY: smoke prepare index baseline agent eval distill train_student eval_student ablations all clean

smoke:
	bash scripts/run_smoke.sh

prepare:
	$(PYTHON) scripts/prepare_minilongbench.py --out data/minilongbench_{split}.jsonl --split all --mode remote

index:
	$(PYTHON) scripts/build_corpus.py --in data/minilongbench_train.jsonl --out data/corpus_chunks.jsonl --index_dir data/index/

baseline:
	$(PYTHON) run_baseline_rag.py --config configs/baseline_rag.yaml --dataset data/minilongbench_test.jsonl --index_dir data/index --out results/baseline_rag.jsonl

agent:
	$(PYTHON) run_agent.py --config configs/agent.yaml --dataset data/minilongbench_test.jsonl --index_dir data/index --out results/edge_agent.jsonl

eval:
	$(PYTHON) evaluate.py --gold data/minilongbench_test.jsonl --pred results/baseline_rag.jsonl results/edge_agent.jsonl --out_dir report/

distill:
	$(PYTHON) scripts/distill_controller_data.py --teacher_config configs/teacher_distill.yaml --dataset data/minilongbench_train.jsonl --out data/student_train.jsonl

train_student:
	$(PYTHON) train_student.py --config configs/train_qlora.yaml --train data/student_train.jsonl --out_dir checkpoints/student

eval_student:
	$(PYTHON) scripts/eval_student_controller.py --agent_config configs/agent.yaml --dataset data/minilongbench_test.jsonl --checkpoint checkpoints/student --out_dir report_student/

ablations:
	bash scripts/run_ablations.sh data/minilongbench_test.jsonl data/index

all: prepare index baseline agent eval ablations distill train_student eval_student

clean:
	rm -rf results report report_tiny report_student checkpoints data/index data/corpus_chunks.jsonl data/minilongbench_train.jsonl data/minilongbench_valid.jsonl data/minilongbench_test.jsonl data/student_train.jsonl data/student_train_stats.json results/ablations
