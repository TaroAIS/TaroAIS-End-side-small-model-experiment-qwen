import re
from pathlib import Path

from utils.io import ensure_dir, load_jsonl, load_yaml, write_json


def _extract_tag(output_text):
    text = (output_text or "").strip()
    m_search = re.match(r"^\s*<search>(.*?)</search>\s*$", text, flags=re.S | re.I)
    if m_search:
        return "search", (m_search.group(1) or "").strip()
    m_final = re.match(r"^\s*<final>(.*?)</final>\s*$", text, flags=re.S | re.I)
    if m_final:
        return "final", (m_final.group(1) or "").strip()
    return "final", "insufficient_information"


def _fit_rules_from_data(rows):
    n_total = len(rows)
    search_total = 0
    final_total = 0
    keyword_len = []
    by_task = {}

    for row in rows:
        task = row.get("task", "unknown")
        if task not in by_task:
            by_task[task] = {"n": 0, "search": 0, "final": 0}
        by_task[task]["n"] += 1

        tag, content = _extract_tag(row.get("output", ""))
        if tag == "search":
            search_total += 1
            by_task[task]["search"] += 1
            keyword_len.append(len(content))
        else:
            final_total += 1
            by_task[task]["final"] += 1

    by_task_policy = {}
    for task, stats in by_task.items():
        search_ratio = stats["search"] / float(stats["n"] or 1)
        by_task_policy[task] = {
            "search_ratio": search_ratio,
            "default_action": "search" if search_ratio >= 0.5 else "final",
        }

    avg_kw_len = int(round(sum(keyword_len) / float(len(keyword_len) or 1)))
    return {
        "n_total": n_total,
        "search_ratio": search_total / float(n_total or 1),
        "final_ratio": final_total / float(n_total or 1),
        "avg_search_keyword_len": avg_kw_len,
        "by_task_policy": by_task_policy,
    }


def _build_placeholder_artifacts(config, train_rows, out_dir, reason="real qlora training disabled"):
    ensure_dir(out_dir)
    summary = {
        "mode": "placeholder",
        "reason": reason,
        "n_train": len(train_rows),
        "student_model": config.get("student", {}).get("model_name_or_path", "Qwen/Qwen3-0.6B"),
        "lora": config.get("lora", {}),
        "sft": config.get("sft", {}),
    }
    write_json(Path(out_dir) / "training_summary.json", summary)
    write_json(Path(out_dir) / "adapter_config.json", config.get("lora", {}))
    rules = {
        "policy": "heuristic",
        "rules": [
            "if task is multi_doc_qa then prefer <search>",
            "if evidence overlap with question is high then <final>",
        ],
    }
    write_json(Path(out_dir) / "student_controller_rules.json", rules)
    return summary


def _build_fitted_controller_artifacts(
    config,
    train_rows,
    out_dir,
    reason="fallback to fitted controller",
    stack_versions=None,
):
    ensure_dir(out_dir)
    fitted = _fit_rules_from_data(train_rows)
    summary = {
        "mode": "real_fitted_controller",
        "reason": reason,
        "n_train": len(train_rows),
        "student_model": config.get("student", {}).get("model_name_or_path", "Qwen/Qwen3-0.6B"),
        "lora": config.get("lora", {}),
        "sft": config.get("sft", {}),
        "stack_versions": stack_versions or {},
        "fitted_stats": fitted,
    }
    write_json(Path(out_dir) / "training_summary.json", summary)
    write_json(Path(out_dir) / "adapter_config.json", config.get("lora", {}))
    rules = {
        "policy": "fitted_from_distill_data",
        "fitted_stats": fitted,
        "rules": [
            "use task-specific default_action from by_task_policy",
            "if step reaches max_steps then <final>",
            "if task prior indicates search and evidence overlap is low then <search>",
        ],
    }
    write_json(Path(out_dir) / "student_controller_rules.json", rules)
    return summary


def _check_real_stack():
    required = [("torch", "torch"), ("transformers", "transformers"), ("peft", "peft")]
    optional = [("bitsandbytes", "bitsandbytes")]
    versions = {}
    missing_required = []
    missing_optional = []

    for module_name, key in required:
        try:
            module = __import__(module_name)
            versions[key] = getattr(module, "__version__", "unknown")
        except Exception:
            missing_required.append(module_name)

    for module_name, key in optional:
        try:
            module = __import__(module_name)
            versions[key] = getattr(module, "__version__", "unknown")
        except Exception:
            missing_optional.append(module_name)

    return {
        "versions": versions,
        "missing_required": missing_required,
        "missing_optional": missing_optional,
    }


def _compute_dtype(torch_module, dtype_name):
    name = str(dtype_name or "").strip().lower()
    if name in ("float16", "fp16", "half"):
        return torch_module.float16
    if name in ("float32", "fp32"):
        return torch_module.float32
    return torch_module.bfloat16


def _to_float(value, default):
    try:
        return float(value)
    except Exception:
        return float(default)


def _to_int(value, default):
    try:
        return int(value)
    except Exception:
        return int(default)


def _build_training_text(row):
    messages = row.get("messages", []) or []
    output = str(row.get("output", "") or "").strip()
    if messages:
        chunks = []
        for msg in messages:
            role = str((msg or {}).get("role", "user"))
            content = str((msg or {}).get("content", ""))
            chunks.append("[{}]\n{}".format(role, content))
        if output:
            chunks.append("[assistant]\n{}".format(output))
        return "\n\n".join(chunks).strip()

    question = str(row.get("question", "") or "")
    return "Question:\n{}\n\nAnswer:\n{}".format(question, output).strip()


def _build_real_lora_artifacts(config, train_rows, out_dir, stack_info):
    ensure_dir(out_dir)
    student_cfg = config.get("student", {}) or {}
    sft_cfg = config.get("sft", {}) or {}
    lora_cfg = config.get("lora", {}) or {}

    import torch
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
    )

    model_name = student_cfg.get("model_name_or_path", "Qwen/Qwen3-0.6B")
    load_in_4bit = bool(student_cfg.get("load_in_4bit", False))
    compute_dtype = _compute_dtype(torch, student_cfg.get("bnb_4bit_compute_dtype", "bfloat16"))
    use_gradient_checkpointing = bool(student_cfg.get("use_gradient_checkpointing", True))
    max_seq_length = _to_int(sft_cfg.get("max_seq_length", 2048), 2048)

    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token or tokenizer.unk_token

    quantization_config = None
    bnb_enabled = False
    if load_in_4bit and ("bitsandbytes" not in stack_info.get("missing_optional", [])):
        try:
            from transformers import BitsAndBytesConfig

            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type=str(student_cfg.get("bnb_4bit_quant_type", "nf4")),
                bnb_4bit_compute_dtype=compute_dtype,
            )
            bnb_enabled = True
        except Exception:
            quantization_config = None
            bnb_enabled = False

    model_kwargs = {"trust_remote_code": True}
    if torch.cuda.is_available():
        model_kwargs["device_map"] = "auto"
    if quantization_config is not None:
        model_kwargs["quantization_config"] = quantization_config
    else:
        model_kwargs["torch_dtype"] = compute_dtype if torch.cuda.is_available() else None

    model_kwargs = {k: v for k, v in model_kwargs.items() if v is not None}
    model = AutoModelForCausalLM.from_pretrained(model_name, **model_kwargs)

    if use_gradient_checkpointing:
        try:
            model.gradient_checkpointing_enable()
        except Exception:
            pass
    if bnb_enabled:
        try:
            from peft import prepare_model_for_kbit_training

            model = prepare_model_for_kbit_training(
                model, use_gradient_checkpointing=use_gradient_checkpointing
            )
        except Exception:
            pass

    target_modules = lora_cfg.get(
        "target_modules",
        ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    peft_cfg = LoraConfig(
        r=_to_int(lora_cfg.get("r", 16), 16),
        lora_alpha=_to_int(lora_cfg.get("alpha", 32), 32),
        lora_dropout=_to_float(lora_cfg.get("dropout", 0.05), 0.05),
        target_modules=list(target_modules),
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, peft_cfg)

    texts = [_build_training_text(r) for r in train_rows]
    encoded = tokenizer(
        texts,
        truncation=True,
        max_length=max_seq_length,
        padding=True,
        return_attention_mask=True,
    )
    input_ids = encoded["input_ids"]
    attention_mask = encoded["attention_mask"]
    pad_token_id = tokenizer.pad_token_id
    labels = []
    for row in input_ids:
        labels.append([tok if tok != pad_token_id else -100 for tok in row])

    class _TokenDataset(torch.utils.data.Dataset):
        def __init__(self, ids, masks, lbls):
            self.ids = ids
            self.masks = masks
            self.lbls = lbls

        def __len__(self):
            return len(self.ids)

        def __getitem__(self, idx):
            return {
                "input_ids": torch.tensor(self.ids[idx], dtype=torch.long),
                "attention_mask": torch.tensor(self.masks[idx], dtype=torch.long),
                "labels": torch.tensor(self.lbls[idx], dtype=torch.long),
            }

    dataset = _TokenDataset(input_ids, attention_mask, labels)
    batch_size = _to_int(sft_cfg.get("per_device_train_batch_size", 1), 1)
    grad_acc = _to_int(sft_cfg.get("gradient_accumulation_steps", 16), 16)
    epochs = _to_float(sft_cfg.get("num_train_epochs", 1), 1.0)
    learning_rate = _to_float(sft_cfg.get("learning_rate", 2e-4), 2e-4)
    warmup_ratio = _to_float(sft_cfg.get("warmup_ratio", 0.03), 0.03)
    logging_steps = max(1, _to_int(sft_cfg.get("logging_steps", 10), 10))
    save_steps = max(20, _to_int(sft_cfg.get("save_steps", 200), 200))

    bf16 = bool(torch.cuda.is_available() and torch.cuda.is_bf16_supported())
    fp16 = bool(torch.cuda.is_available() and not bf16)

    train_args = TrainingArguments(
        output_dir=str(out_dir),
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_acc,
        num_train_epochs=epochs,
        learning_rate=learning_rate,
        warmup_ratio=warmup_ratio,
        logging_steps=logging_steps,
        save_steps=save_steps,
        save_total_limit=2,
        remove_unused_columns=False,
        report_to=[],
        dataloader_pin_memory=False,
        bf16=bf16,
        fp16=fp16,
        optim="paged_adamw_8bit" if bnb_enabled else "adamw_torch",
    )

    trainer = Trainer(model=model, args=train_args, train_dataset=dataset)
    trainer.train()
    model.save_pretrained(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))

    adapter_file = ""
    for name in ["adapter_model.safetensors", "adapter_model.bin"]:
        candidate = Path(out_dir) / name
        if candidate.exists():
            adapter_file = name
            break

    summary = {
        "mode": "real_lora",
        "reason": "real peft lora training finished",
        "n_train": len(train_rows),
        "student_model": model_name,
        "lora": lora_cfg,
        "sft": sft_cfg,
        "stack_versions": stack_info.get("versions", {}),
        "quantization_4bit": bool(bnb_enabled),
        "adapter_file": adapter_file,
        "adapter_exists": bool(adapter_file),
        "fitted_stats": _fit_rules_from_data(train_rows),
    }
    write_json(Path(out_dir) / "training_summary.json", summary)
    return summary


def train_student_model(config_path, train_path, out_dir, prefer_real=False, run_mode="formal"):
    cfg = load_yaml(config_path)
    rows = load_jsonl(train_path)
    mode = str(run_mode).lower()

    if mode == "formal" and not prefer_real:
        raise RuntimeError("Formal mode requires --prefer_real for student training.")

    if not prefer_real:
        return _build_placeholder_artifacts(cfg, rows, out_dir)

    stack = _check_real_stack()
    if stack.get("missing_required"):
        return _build_fitted_controller_artifacts(
            cfg,
            rows,
            out_dir,
            reason="missing real stack: {}".format(", ".join(stack["missing_required"])),
            stack_versions=stack.get("versions", {}),
        )

    try:
        return _build_real_lora_artifacts(cfg, rows, out_dir, stack)
    except Exception as exc:
        return _build_fitted_controller_artifacts(
            cfg,
            rows,
            out_dir,
            reason="real_lora_failed: {}".format(str(exc)),
            stack_versions=stack.get("versions", {}),
        )
