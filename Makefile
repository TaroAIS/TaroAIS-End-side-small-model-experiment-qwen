SHELL := /bin/bash
PYTHON ?= python3

.PHONY: smoke preflight prepare prepare_strict index baseline compare_controls agent eval distill train_student eval_student ablations bench_key calibrate main_formal student_branch all all_formal all_plus_student all_smoke clean

smoke:
	bash scripts/cmd/smoke.sh

preflight:
	bash scripts/cmd/preflight_formal.sh

prepare:
	bash scripts/cmd/prepare_remote.sh

prepare_strict:
	bash scripts/cmd/prepare_remote_strict.sh

index:
	bash scripts/cmd/index.sh

baseline:
	bash scripts/cmd/baseline.sh

compare_controls:
	bash scripts/cmd/compare_controls.sh

agent:
	bash scripts/cmd/agent.sh

eval:
	bash scripts/cmd/eval.sh

distill:
	bash scripts/cmd/distill.sh

train_student:
	bash scripts/cmd/train_student.sh

eval_student:
	bash scripts/cmd/eval_student.sh

ablations:
	bash scripts/cmd/ablations.sh

bench_key:
	bash scripts/cmd/bench_key_tasks.sh

calibrate:
	bash scripts/cmd/calibrate_thresholds.sh

main_formal:
	bash scripts/cmd/main_formal.sh

student_branch:
	bash scripts/cmd/student_branch.sh

all_smoke:
	bash scripts/cmd/smoke.sh

all_formal:
	bash scripts/cmd/main_formal.sh

all_plus_student:
	bash scripts/cmd/main_formal.sh
	bash scripts/cmd/student_branch.sh

all: all_formal

clean:
	rm -rf results report report_tiny report_student report_key_supp report_calibration checkpoints data/index data/corpus_chunks.jsonl data/student_train.jsonl data/student_train_stats.json
