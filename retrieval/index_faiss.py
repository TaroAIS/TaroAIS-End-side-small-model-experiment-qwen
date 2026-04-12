import os
from collections import Counter
import math
from pathlib import Path

try:
    import numpy as np
except Exception:
    np = None

from retrieval.chunking import build_chunks_from_dataset
from utils.io import dump_jsonl, ensure_dir, load_jsonl, read_json, write_json


class RetrievalIndex(object):
    _ST_MODEL_CACHE = {}

    def __init__(
        self,
        embedding_model="sentence-transformers",
        index_type="faiss",
        hybrid_cfg=None,
        runtime_mode="formal",
        require_dense_in_formal=False,
    ):
        self.embedding_model = embedding_model
        self.index_type = index_type
        self.mode = "lexical"
        self.chunks = []
        self._token_bags = []
        self._st_model = None
        self._embeddings = None
        self._faiss_index = None
        self.runtime_mode = str(runtime_mode or "formal").lower()
        self.require_dense_in_formal = bool(require_dense_in_formal)

        hybrid_cfg = hybrid_cfg or {}
        self.hybrid_cfg = dict(hybrid_cfg)
        self.hybrid_enable = bool(self.hybrid_cfg.get("enable", False))
        self.hybrid_alpha_dense = float(self.hybrid_cfg.get("alpha_dense", 0.65))
        self.hybrid_alpha_lexical = float(self.hybrid_cfg.get("alpha_lexical", 0.35))
        self.hybrid_max_candidates = max(1, int(self.hybrid_cfg.get("max_candidates", 20)))
        self.hybrid_dedup_by_chunk_id = bool(self.hybrid_cfg.get("dedup_by_chunk_id", True))

        if (self.hybrid_alpha_dense + self.hybrid_alpha_lexical) <= 0:
            self.hybrid_alpha_dense = 0.65
            self.hybrid_alpha_lexical = 0.35

    @staticmethod
    def _tokenize(text):
        text = (text or "").strip().lower()
        if not text:
            return []
        if " " in text:
            tokens = [t for t in text.split(" ") if t]
        else:
            tokens = [ch for ch in text if ch.strip()]
        return tokens

    @classmethod
    def _lexical_score(cls, q, d):
        q_bag = Counter(cls._tokenize(q))
        d_bag = d
        if not q_bag or not d_bag:
            return 0.0
        overlap = 0.0
        for tok, q_cnt in q_bag.items():
            overlap += min(float(q_cnt), float(d_bag.get(tok, 0)))
        denom = math.sqrt(sum(v * v for v in q_bag.values()) * sum(v * v for v in d_bag.values()))
        if denom <= 0:
            return 0.0
        return float(overlap / denom)

    @staticmethod
    def _clip01(value):
        v = float(value)
        if v < 0.0:
            return 0.0
        if v > 1.0:
            return 1.0
        return v

    def _dense_available(self):
        return (
            np is not None
            and self._st_model is not None
            and self._embeddings is not None
            and len(self.chunks) > 0
        )

    def _require_dense_or_raise(self, reason):
        if self.require_dense_in_formal and self.runtime_mode == "formal":
            raise RuntimeError(
                "Dense retrieval required in formal mode but unavailable: {}".format(reason)
            )

    @staticmethod
    def _default_st_model_name():
        return "sentence-transformers/all-MiniLM-L6-v2"

    @classmethod
    def _resolve_local_st_path(cls, model_name):
        normalized = str(model_name or "").strip()
        if normalized in ("", "sentence-transformers", cls._default_st_model_name()):
            snapshot_root = (
                Path.home()
                / ".cache"
                / "huggingface"
                / "hub"
                / "models--sentence-transformers--all-MiniLM-L6-v2"
                / "snapshots"
            )
            if snapshot_root.exists():
                for child in sorted(snapshot_root.iterdir()):
                    if not child.is_dir():
                        continue
                    if (child / "modules.json").exists() and (child / "config.json").exists():
                        return str(child)
        return normalized or cls._default_st_model_name()

    def _try_dense_setup(self):
        if np is None:
            return False
        try:
            from sentence_transformers import SentenceTransformer

            model_name = self.embedding_model
            if model_name in ("sentence-transformers", "", None):
                model_name = self._default_st_model_name()
            model_name = self._resolve_local_st_path(model_name)
            cache_key = str(model_name)
            if cache_key not in self._ST_MODEL_CACHE:
                kwargs = {}
                if os.path.isdir(cache_key):
                    kwargs["local_files_only"] = True
                self._ST_MODEL_CACHE[cache_key] = SentenceTransformer(cache_key, **kwargs)
            self._st_model = self._ST_MODEL_CACHE[cache_key]
            return True
        except Exception:
            self._st_model = None
            return False

    def build(self, chunks):
        self.chunks = list(chunks)
        self._token_bags = [Counter(self._tokenize(c.get("text", ""))) for c in self.chunks]

        if not self.chunks:
            self.mode = "lexical"
            return

        if not self._try_dense_setup():
            self._require_dense_or_raise("sentence-transformers setup failed")
            self.mode = "lexical"
            return

        try:
            vec = self._st_model.encode(
                [c.get("text", "") for c in self.chunks],
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            self._embeddings = np.asarray(vec, dtype="float32")
        except Exception:
            self._embeddings = None
            self._require_dense_or_raise("embedding encode failed")
            self.mode = "lexical"
            return

        if self._embeddings is None:
            self._require_dense_or_raise("embedding array is empty")
            self.mode = "lexical"
            return

        if self.index_type == "faiss":
            try:
                import faiss

                index = faiss.IndexFlatIP(self._embeddings.shape[1])
                index.add(self._embeddings)
                self._faiss_index = index
                self.mode = "faiss"
                return
            except Exception:
                pass

        self.mode = "dense_numpy"

    def _dense_candidates(self, query, top_k):
        if not self._dense_available():
            self._require_dense_or_raise("dense candidates requested with no dense state")
            return []

        k = min(max(1, int(top_k)), len(self.chunks))
        if self.mode == "faiss" and self._faiss_index is not None:
            qv = self._st_model.encode([query], normalize_embeddings=True, show_progress_bar=False)
            qv = np.asarray(qv, dtype="float32")
            score, idx = self._faiss_index.search(qv, k)
            out = []
            for s, i in zip(score[0].tolist(), idx[0].tolist()):
                if i < 0:
                    continue
                out.append((int(i), float(s)))
            return out

        if self.mode in ("dense_numpy", "faiss"):
            qv = self._st_model.encode([query], normalize_embeddings=True, show_progress_bar=False)
            qv = np.asarray(qv, dtype="float32")[0]
            score = np.dot(self._embeddings, qv)
            idx = np.argsort(-score)[:k]
            return [(int(i), float(score[i])) for i in idx.tolist()]

        self._require_dense_or_raise("unexpected dense mode {}".format(self.mode))
        return []

    def _lexical_candidates(self, query, top_k):
        k = min(max(1, int(top_k)), len(self.chunks))
        ranked = []
        for i, bag in enumerate(self._token_bags):
            score = self._lexical_score(query, bag)
            ranked.append((score, i))
        ranked.sort(key=lambda x: x[0], reverse=True)
        return [(int(i), float(s)) for s, i in ranked[:k]]

    def _hybrid_search(self, query, top_k):
        dense_limit = min(
            len(self.chunks),
            max(int(top_k), int(self.hybrid_max_candidates)),
        )
        lexical_limit = dense_limit

        dense_items = self._dense_candidates(query, dense_limit)
        lexical_items = self._lexical_candidates(query, lexical_limit)

        dense_scores = {}
        for idx, score in dense_items:
            dense_scores[idx] = float(score)

        lexical_scores = {}
        for idx, score in lexical_items:
            lexical_scores[idx] = float(score)

        all_idx = set(dense_scores.keys()) | set(lexical_scores.keys())
        mix_rows = []
        for idx in all_idx:
            dense_raw = dense_scores.get(idx, 0.0)
            lexical_raw = lexical_scores.get(idx, 0.0)
            # cosine/IP in [-1,1] -> [0,1], then weighted fusion.
            dense_norm = self._clip01((dense_raw + 1.0) / 2.0)
            lexical_norm = self._clip01(lexical_raw)
            score = (
                self.hybrid_alpha_dense * dense_norm
                + self.hybrid_alpha_lexical * lexical_norm
            )
            mix_rows.append((score, idx, dense_raw, lexical_raw))

        mix_rows.sort(key=lambda x: x[0], reverse=True)
        out = []
        seen_chunk_id = set()
        for score, idx, dense_raw, lexical_raw in mix_rows:
            row = dict(self.chunks[idx])
            if self.hybrid_dedup_by_chunk_id:
                cid = str(row.get("chunk_id", "") or "")
                if cid and cid in seen_chunk_id:
                    continue
                if cid:
                    seen_chunk_id.add(cid)
            row["score"] = float(score)
            row["score_dense"] = float(dense_raw)
            row["score_lexical"] = float(lexical_raw)
            row["score_hybrid"] = float(score)
            out.append(row)
            if len(out) >= int(top_k):
                break
        return out

    def search(self, query, top_k=5):
        k = max(1, int(top_k))
        if not self.chunks:
            return []

        if self.hybrid_enable:
            try:
                return self._hybrid_search(query, k)
            except Exception:
                self._require_dense_or_raise("hybrid search failed")

        if self.mode == "faiss" and self._faiss_index is not None and self._st_model is not None:
            try:
                qv = self._st_model.encode([query], normalize_embeddings=True, show_progress_bar=False)
                qv = np.asarray(qv, dtype="float32")
                score, idx = self._faiss_index.search(qv, min(k, len(self.chunks)))
                out = []
                for s, i in zip(score[0].tolist(), idx[0].tolist()):
                    if i < 0:
                        continue
                    row = dict(self.chunks[i])
                    row["score"] = float(s)
                    out.append(row)
                return out
            except Exception:
                self._require_dense_or_raise("faiss search failed")
                pass

        if (
            self.mode == "dense_numpy"
            and self._embeddings is not None
            and self._st_model is not None
            and np is not None
        ):
            try:
                qv = self._st_model.encode([query], normalize_embeddings=True, show_progress_bar=False)
                qv = np.asarray(qv, dtype="float32")[0]
                score = np.dot(self._embeddings, qv)
                idx = np.argsort(-score)[: min(k, len(score))]
                out = []
                for i in idx.tolist():
                    row = dict(self.chunks[i])
                    row["score"] = float(score[i])
                    out.append(row)
                return out
            except Exception:
                self._require_dense_or_raise("dense numpy search failed")
                pass

        ranked = []
        for row, bag in zip(self.chunks, self._token_bags):
            s = self._lexical_score(query, bag)
            ranked.append((s, row))
        ranked.sort(key=lambda x: x[0], reverse=True)
        out = []
        for s, row in ranked[: min(k, len(ranked))]:
            item = dict(row)
            item["score"] = float(s)
            out.append(item)
        return out

    def save(self, index_dir, chunk_path=None):
        ensure_dir(index_dir)
        if chunk_path is None:
            chunk_path = os.path.join(index_dir, "chunks.jsonl")
        dump_jsonl(chunk_path, self.chunks)

        meta = {
            "mode": self.mode,
            "embedding_model": self.embedding_model,
            "index_type": self.index_type,
            "hybrid": self.hybrid_cfg,
            "runtime_mode": self.runtime_mode,
            "require_dense_in_formal": self.require_dense_in_formal,
            "n_chunks": len(self.chunks),
            "chunk_path": chunk_path,
        }

        emb_path = None
        if self._embeddings is not None and np is not None:
            emb_path = os.path.join(index_dir, "embeddings.npy")
            np.save(emb_path, self._embeddings)
            meta["embeddings_path"] = emb_path

        if self.mode == "faiss" and self._faiss_index is not None:
            try:
                import faiss

                faiss_path = os.path.join(index_dir, "faiss.index")
                faiss.write_index(self._faiss_index, faiss_path)
                meta["faiss_index_path"] = faiss_path
            except Exception:
                pass

        write_json(os.path.join(index_dir, "index_meta.json"), meta)
        return meta

    @classmethod
    def load(cls, index_dir):
        meta_path = os.path.join(index_dir, "index_meta.json")
        if not os.path.exists(meta_path):
            raise FileNotFoundError("index meta not found: {}".format(meta_path))
        meta = read_json(meta_path)
        idx = cls(
            embedding_model=meta.get("embedding_model", "sentence-transformers"),
            index_type=meta.get("index_type", "faiss"),
            hybrid_cfg=meta.get("hybrid", {}),
            runtime_mode=meta.get("runtime_mode", "formal"),
            require_dense_in_formal=meta.get("require_dense_in_formal", False),
        )
        chunk_path = meta.get("chunk_path", os.path.join(index_dir, "chunks.jsonl"))
        idx.chunks = load_jsonl(chunk_path)
        idx._token_bags = [Counter(idx._tokenize(c.get("text", ""))) for c in idx.chunks]

        emb_path = meta.get("embeddings_path")
        if emb_path and os.path.exists(emb_path) and np is not None:
            try:
                idx._embeddings = np.load(emb_path)
                idx.mode = "dense_numpy"
            except Exception:
                idx._embeddings = None

        if meta.get("mode") == "faiss":
            faiss_path = meta.get("faiss_index_path", os.path.join(index_dir, "faiss.index"))
            if os.path.exists(faiss_path):
                try:
                    import faiss

                    idx._faiss_index = faiss.read_index(faiss_path)
                    idx.mode = "faiss"
                except Exception:
                    idx._faiss_index = None

        if idx.mode in (None, ""):
            idx.mode = meta.get("mode", "lexical")
        if idx.mode not in ("faiss", "dense_numpy", "lexical"):
            idx.mode = "lexical"
        return idx


def build_and_save_index(
    dataset_rows,
    out_chunk_path,
    index_dir,
    chunk_size=512,
    chunk_overlap=128,
    embedding_model="sentence-transformers",
    index_type="faiss",
    hybrid_cfg=None,
    runtime_mode="formal",
    require_dense_in_formal=False,
):
    chunks = build_chunks_from_dataset(
        dataset_rows,
        chunk_size=int(chunk_size),
        overlap=int(chunk_overlap),
    )
    idx = RetrievalIndex(
        embedding_model=embedding_model,
        index_type=index_type,
        hybrid_cfg=hybrid_cfg,
        runtime_mode=runtime_mode,
        require_dense_in_formal=require_dense_in_formal,
    )
    idx.build(chunks)
    idx.save(index_dir=index_dir, chunk_path=out_chunk_path)
    return chunks, idx
