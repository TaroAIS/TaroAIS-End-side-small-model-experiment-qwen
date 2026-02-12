import os
from collections import Counter
import math

try:
    import numpy as np
except Exception:
    np = None

from retrieval.chunking import build_chunks_from_dataset
from utils.io import dump_jsonl, ensure_dir, load_jsonl, read_json, write_json


class RetrievalIndex(object):
    def __init__(self, embedding_model="sentence-transformers", index_type="faiss"):
        self.embedding_model = embedding_model
        self.index_type = index_type
        self.mode = "lexical"
        self.chunks = []
        self._token_bags = []
        self._st_model = None
        self._embeddings = None
        self._faiss_index = None

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

    def _try_dense_setup(self):
        if np is None:
            return False
        try:
            from sentence_transformers import SentenceTransformer

            model_name = self.embedding_model
            if model_name in ("sentence-transformers", "", None):
                model_name = "sentence-transformers/all-MiniLM-L6-v2"
            self._st_model = SentenceTransformer(model_name)
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
            self.mode = "lexical"
            return

        if self._embeddings is None:
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

    def search(self, query, top_k=5):
        k = max(1, int(top_k))
        if not self.chunks:
            return []

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


def build_and_save_index(dataset_rows, out_chunk_path, index_dir, chunk_size=512, chunk_overlap=128, embedding_model="sentence-transformers", index_type="faiss"):
    chunks = build_chunks_from_dataset(
        dataset_rows,
        chunk_size=int(chunk_size),
        overlap=int(chunk_overlap),
    )
    idx = RetrievalIndex(embedding_model=embedding_model, index_type=index_type)
    idx.build(chunks)
    idx.save(index_dir=index_dir, chunk_path=out_chunk_path)
    return chunks, idx
