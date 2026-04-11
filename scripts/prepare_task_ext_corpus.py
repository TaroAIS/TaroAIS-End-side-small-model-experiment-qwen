#!/usr/bin/env python3
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dataset_upgrade_common import (
    EXT_DATASET_SPECS,
    dataset_row,
    download_jsonl_rows,
    download_zip,
    dump_rows,
    ensure_python,
    hf_api_payload,
    load_parquet_rows,
    normalize_answer,
    parquet_file_urls,
    rows_api_iter,
    safe_text,
    split_train_valid,
)
from utils.io import write_json
from utils.runtime import schema_path
from utils.schema import validate_records


def _join_lines(items):
    return "\n".join([safe_text(x) for x in items if safe_text(x)])


def _pick_qasper_answer(answer_block):
    answer_candidates = ensure_python(answer_block.get("answer", []))
    for item in answer_candidates:
        item = ensure_python(item)
        if item.get("unanswerable", False):
            continue
        free_form = safe_text(item.get("free_form_answer", ""))
        if free_form:
            return free_form
        spans = item.get("extractive_spans", []) or []
        span_text = normalize_answer(spans)
        if span_text:
            return span_text
        yes_no = item.get("yes_no")
        if yes_no is not None:
            return "yes" if bool(yes_no) else "no"
    return ""


def _narrativeqa_rows(split, max_rows=0, use_full_text=True):
    spec = EXT_DATASET_SPECS["narrativeqa"]
    prefix = spec["train_prefix"] if split == "train" else spec["valid_prefix"]
    urls, payload = parquet_file_urls(spec["dataset_id"], prefix)
    source_rows = load_parquet_rows(urls, max_rows=max_rows)

    full_text_map = {}
    if use_full_text and source_rows:
        wanted_ids = set([safe_text((row.get("document") or {}).get("id", "")) for row in source_rows])
        zip_file = download_zip(spec["dataset_id"], "data/narrativeqa_full_text.zip")
        for name in zip_file.namelist():
            if not name.endswith(".content"):
                continue
            doc_id = Path(name).stem
            if doc_id not in wanted_ids:
                continue
            full_text_map[doc_id] = zip_file.read(name).decode("utf-8", errors="ignore")

    rows = []
    for raw in source_rows:
        document = ensure_python(raw.get("document", {}))
        question = ensure_python(raw.get("question", {}))
        answers = ensure_python(raw.get("answers", []))
        doc_id = safe_text(document.get("id", ""))
        answer = ""
        for item in answers:
            text = safe_text(ensure_python(item).get("text", ""))
            if text:
                answer = text
                break
        full_text = safe_text(full_text_map.get(doc_id, ""))
        if not full_text:
            full_text = safe_text((document.get("summary") or {}).get("text", ""))
        rows.append(
            dataset_row(
                sample_id="nqa_{}_{}".format(split, doc_id or len(rows)),
                task="single_doc_qa",
                question=safe_text(question.get("text", "")),
                documents=[
                    {
                        "doc_id": doc_id or "d1",
                        "text": full_text,
                    }
                ],
                answer=answer,
                meta={
                    "source": spec["source"],
                    "source_split": split,
                    "source_task": "narrativeqa",
                    "task_group": spec["task_group"],
                    "source_kind": safe_text(document.get("kind", "")),
                    "source_url": safe_text(document.get("url", "")),
                    "uses_full_text": bool(doc_id in full_text_map),
                },
            )
        )
    return rows, payload


def _qasper_rows(split, max_rows=0):
    spec = EXT_DATASET_SPECS["qasper"]
    payload = hf_api_payload(spec["dataset_id"])
    rows = []
    for paper in rows_api_iter(spec["dataset_id"], spec["config"], spec["train_split"] if split == "train" else spec["valid_split"], max_rows=max_rows, page_size=50):
        title = safe_text(paper.get("title", ""))
        abstract = safe_text(paper.get("abstract", ""))
        full_text = ensure_python(paper.get("full_text", {}))
        qas = ensure_python(paper.get("qas", {}))
        section_names = full_text.get("section_name", []) or []
        section_paragraphs = full_text.get("paragraphs", []) or []
        documents = []
        if abstract:
            documents.append({"doc_id": "abstract", "text": abstract})
        for idx, section_name in enumerate(section_names):
            paragraphs = section_paragraphs[idx] if idx < len(section_paragraphs) else []
            paragraphs = ensure_python(paragraphs)
            text = _join_lines(paragraphs)
            if not text:
                continue
            documents.append(
                {
                    "doc_id": "sec_{:02d}".format(idx + 1),
                    "text": "{}\n{}".format(safe_text(section_name), text).strip(),
                }
            )
        questions = qas.get("question", []) or []
        question_ids = qas.get("question_id", []) or []
        answers = qas.get("answers", []) or []
        for idx, question in enumerate(questions):
            answer_block = ensure_python(answers[idx]) if idx < len(answers) else {}
            answer = _pick_qasper_answer(answer_block)
            if not answer:
                continue
            question_id = safe_text(question_ids[idx]) if idx < len(question_ids) else str(idx)
            rows.append(
                dataset_row(
                    sample_id="qasper_{}_{}_{}".format(split, safe_text(paper.get("id", "")), question_id[:24]),
                    task="single_doc_qa",
                    question=safe_text(question),
                    documents=documents,
                    answer=answer,
                    meta={
                        "source": spec["source"],
                        "source_split": split,
                        "source_task": "qasper",
                        "task_group": spec["task_group"],
                        "paper_id": safe_text(paper.get("id", "")),
                        "paper_title": title,
                    },
                )
            )
            if max_rows and len(rows) >= int(max_rows):
                return rows, payload
    return rows, payload


def _hotpotqa_rows(split, max_rows=0):
    spec = EXT_DATASET_SPECS["hotpotqa"]
    prefix = spec["train_prefix"] if split == "train" else spec["valid_prefix"]
    urls, payload = parquet_file_urls(spec["dataset_id"], prefix)
    source_rows = load_parquet_rows(urls, max_rows=max_rows)
    rows = []
    for raw in source_rows:
        context = ensure_python(raw.get("context", {}))
        titles = ensure_python(context.get("title", []))
        sentences = ensure_python(context.get("sentences", []))
        documents = []
        for idx, title in enumerate(titles):
            sent_list = ensure_python(sentences[idx]) if idx < len(sentences) else []
            text = _join_lines(sent_list)
            if not text:
                continue
            documents.append({"doc_id": safe_text(title) or "doc{}".format(idx + 1), "text": text})
        rows.append(
            dataset_row(
                sample_id="hpqa_{}_{}".format(split, safe_text(raw.get("id", ""))),
                task="multi_doc_qa",
                question=safe_text(raw.get("question", "")),
                documents=documents,
                answer=safe_text(raw.get("answer", "")),
                meta={
                    "source": spec["source"],
                    "source_split": split,
                    "source_task": "hotpotqa",
                    "task_group": spec["task_group"],
                    "hotpot_type": safe_text(raw.get("type", "")),
                    "hotpot_level": safe_text(raw.get("level", "")),
                },
            )
        )
    return rows, payload


def _musique_rows(split, max_rows=0):
    spec = EXT_DATASET_SPECS["musique"]
    rel_path = spec["train_path"] if split == "train" else spec["valid_path"]
    payload = hf_api_payload(spec["dataset_id"])
    source_rows = download_jsonl_rows(spec["dataset_id"], rel_path, max_rows=max_rows)
    rows = []
    for raw in source_rows:
        paragraphs = ensure_python(raw.get("paragraphs", []))
        documents = []
        for idx, para in enumerate(paragraphs):
            para = ensure_python(para)
            text = safe_text(para.get("paragraph_text", ""))
            if not text:
                continue
            title = safe_text(para.get("title", ""))
            documents.append(
                {
                    "doc_id": title or "para{}".format(idx + 1),
                    "text": "{}\n{}".format(title, text).strip(),
                }
            )
        rows.append(
            dataset_row(
                sample_id="musique_{}_{}".format(split, safe_text(raw.get("id", ""))),
                task="multi_doc_qa",
                question=safe_text(raw.get("question", "")),
                documents=documents,
                answer=safe_text(raw.get("answer", "")),
                meta={
                    "source": spec["source"],
                    "source_split": split,
                    "source_task": "musique",
                    "task_group": spec["task_group"],
                },
            )
        )
    return rows, payload


def _repobench_all_rows(spec_key, max_rows=0):
    spec = EXT_DATASET_SPECS[spec_key]
    urls, payload = parquet_file_urls(spec["dataset_id"], spec["all_prefixes"])
    source_rows = load_parquet_rows(urls, max_rows=max_rows)
    rows = []
    for raw in source_rows:
        documents = []
        prefix = "Repository: {}\nTarget file: {}\nImports:\n{}\nCurrent code prefix:\n{}".format(
            safe_text(raw.get("repo_name", "")),
            safe_text(raw.get("file_path", "")),
            safe_text(raw.get("import_statement", "")),
            safe_text(raw.get("cropped_code", "")),
        ).strip()
        documents.append({"doc_id": "target_prefix", "text": prefix})
        for idx, ctx in enumerate(ensure_python(raw.get("context", []))):
            ctx = ensure_python(ctx)
            text = "Path: {}\nIdentifier: {}\nSnippet:\n{}".format(
                safe_text(ctx.get("path", "")),
                safe_text(ctx.get("identifier", "")),
                safe_text(ctx.get("snippet", "")),
            ).strip()
            if not text:
                continue
            documents.append({"doc_id": "ctx_{:02d}".format(idx + 1), "text": text})
        sample_id = "repobench_{}_{}_{}".format(
            spec["language"],
            safe_text(raw.get("repo_name", "")).replace("/", "_")[:24],
            len(rows),
        )
        rows.append(
            dataset_row(
                sample_id=sample_id,
                task="code_qa",
                question="Based on the repository context, what is the next line of code in `{}`?".format(
                    safe_text(raw.get("file_path", "")) or "the target file"
                ),
                documents=documents,
                answer=safe_text(raw.get("next_line", "")),
                meta={
                    "source": spec["source"],
                    "source_split": "derived",
                    "source_task": "repobench",
                    "task_group": spec["task_group"],
                    "repo_name": safe_text(raw.get("repo_name", "")),
                    "file_path": safe_text(raw.get("file_path", "")),
                    "source_level": safe_text(raw.get("level", "")),
                    "source_language": spec["language"],
                },
            )
        )
    return rows, payload


def _write_group_files(out_root, group_name, dataset_name, train_rows, valid_rows):
    group_dir = Path(out_root) / group_name
    train_path = group_dir / "{}_train.jsonl".format(dataset_name)
    valid_path = group_dir / "{}_valid.jsonl".format(dataset_name)
    dump_rows(train_path, train_rows)
    dump_rows(valid_path, valid_rows)
    return str(train_path), str(valid_path)


def main():
    parser = argparse.ArgumentParser(description="Prepare extension train/valid corpora for long-document tasks.")
    parser.add_argument("--out_root", default="data/train_ext")
    parser.add_argument("--registry", default="data/manifests/dataset_registry.json")
    parser.add_argument("--versions", default="data/manifests/dataset_versions.json")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max_samples", type=int, default=0)
    parser.add_argument("--narrativeqa_summary_only", action="store_true")
    args = parser.parse_args()

    grouped_train = defaultdict(list)
    grouped_valid = defaultdict(list)
    registry_path = Path(args.registry)
    if registry_path.exists():
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
        except Exception:
            registry = {}
    else:
        registry = {}
    registry["train_ext"] = {"groups": {}}

    versions_path = Path(args.versions)
    if versions_path.exists():
        try:
            versions = json.loads(versions_path.read_text(encoding="utf-8"))
        except Exception:
            versions = {}
    else:
        versions = {}
    versions["generated_by"] = "scripts/prepare_task_ext_corpus.py"
    versions["seed"] = int(args.seed)
    versions["datasets"] = {}

    nqa_train, nqa_meta = _narrativeqa_rows("train", max_rows=args.max_samples, use_full_text=not args.narrativeqa_summary_only)
    nqa_valid, _ = _narrativeqa_rows("valid", max_rows=args.max_samples, use_full_text=not args.narrativeqa_summary_only)
    qasper_train, qasper_meta = _qasper_rows("train", max_rows=args.max_samples)
    qasper_valid, _ = _qasper_rows("valid", max_rows=args.max_samples)
    hotpot_train, hotpot_meta = _hotpotqa_rows("train", max_rows=args.max_samples)
    hotpot_valid, _ = _hotpotqa_rows("valid", max_rows=args.max_samples)
    musique_train, musique_meta = _musique_rows("train", max_rows=args.max_samples)
    musique_valid, _ = _musique_rows("valid", max_rows=args.max_samples)
    repopy_all, repopy_meta = _repobench_all_rows("repobench_python", max_rows=args.max_samples)
    repojava_all, repojava_meta = _repobench_all_rows("repobench_java", max_rows=args.max_samples)

    repopy_train, repopy_valid = split_train_valid(
        repopy_all,
        seed=args.seed,
        valid_ratio=0.1,
        stratify_key_fn=lambda row: "{}|{}".format(row.get("task", ""), row.get("meta", {}).get("source_level", "")),
    )
    repojava_train, repojava_valid = split_train_valid(
        repojava_all,
        seed=args.seed,
        valid_ratio=0.1,
        stratify_key_fn=lambda row: "{}|{}".format(row.get("task", ""), row.get("meta", {}).get("source_level", "")),
    )

    dataset_outputs = [
        ("single_doc", "narrativeqa", nqa_train, nqa_valid, nqa_meta, "deepmind/narrativeqa"),
        ("single_doc", "qasper", qasper_train, qasper_valid, qasper_meta, "allenai/qasper"),
        ("multi_doc", "hotpotqa", hotpot_train, hotpot_valid, hotpot_meta, "hotpotqa/hotpot_qa"),
        ("multi_doc", "musique", musique_train, musique_valid, musique_meta, "dgslibisey/MuSiQue"),
        ("code_qa", "repobench_python", repopy_train, repopy_valid, repopy_meta, "tianyang/repobench_python_v1.1"),
        ("code_qa", "repobench_java", repojava_train, repojava_valid, repojava_meta, "tianyang/repobench_java_v1.1"),
    ]

    for group_name, dataset_name, train_rows, valid_rows, payload, dataset_id in dataset_outputs:
        validate_records(train_rows, schema_path("dataset.schema.json"), context_prefix="{}_train".format(dataset_name))
        validate_records(valid_rows, schema_path("dataset.schema.json"), context_prefix="{}_valid".format(dataset_name))
        train_path, valid_path = _write_group_files(args.out_root, group_name, dataset_name, train_rows, valid_rows)
        grouped_train[group_name].extend(train_rows)
        grouped_valid[group_name].extend(valid_rows)
        registry["train_ext"]["groups"].setdefault(group_name, {})
        registry["train_ext"]["groups"][group_name][dataset_name] = {
            "train": train_path,
            "valid": valid_path,
            "dataset_id": dataset_id,
        }
        versions["datasets"][dataset_name] = {
            "dataset_id": dataset_id,
            "revision_resolved": payload.get("sha", "main"),
            "upstream_last_modified": payload.get("lastModified"),
            "n_train": len(train_rows),
            "n_valid": len(valid_rows),
        }

    for group_name in sorted(grouped_train.keys()):
        train_path = Path(args.out_root) / group_name / "merged_train.jsonl"
        valid_path = Path(args.out_root) / group_name / "merged_valid.jsonl"
        dump_rows(train_path, grouped_train[group_name])
        dump_rows(valid_path, grouped_valid[group_name])
        registry["train_ext"]["groups"][group_name]["merged"] = {
            "train": str(train_path),
            "valid": str(valid_path),
        }

    write_json(args.registry, registry)
    write_json(args.versions, versions)

    print("prepared task extension corpora -> {}".format(args.out_root))
    for group_name in sorted(grouped_train.keys()):
        print("{} train={} valid={}".format(group_name, len(grouped_train[group_name]), len(grouped_valid[group_name])))


if __name__ == "__main__":
    main()
