import re
from collections import Counter


def _approx_tokens(text):
    text = text or ""
    return max(1, len(text) // 2)


class MemoryStore(object):
    def __init__(self, strategy="fact_memory", max_prompt_tokens=8000):
        self.strategy = strategy
        self.max_prompt_tokens = int(max_prompt_tokens)
        self.chunks = []
        self._chunk_ids = set()
        self.facts = []
        self.pruning_log = {"strategy": strategy, "dropped": []}

    def add_chunks(self, chunks):
        for c in chunks:
            cid = c.get("chunk_id")
            if cid in self._chunk_ids:
                continue
            self._chunk_ids.add(cid)
            self.chunks.append(dict(c))

    def add_facts(self, facts):
        for f in facts:
            self.facts.append(dict(f))

    def token_count(self):
        s = 0
        for c in self.chunks:
            s += _approx_tokens(c.get("text", ""))
        for f in self.facts:
            s += _approx_tokens(f.get("content", ""))
        return s

    def _support_map(self):
        support = Counter()
        for f in self.facts:
            ev = f.get("evidence", {})
            cid = ev.get("chunk_id")
            if cid:
                support[cid] += 1
        return support

    def prune_to_budget(self):
        dropped = []
        while self.token_count() > self.max_prompt_tokens and self.chunks:
            if self.strategy == "fact_memory":
                support = self._support_map()
                ranked = []
                for idx, c in enumerate(self.chunks):
                    cid = c.get("chunk_id", "")
                    sup = support.get(cid, 0)
                    score = c.get("score", 0.0)
                    ranked.append((sup, score, idx))
                ranked.sort(key=lambda x: (x[0], x[1]))
                _, _, drop_idx = ranked[0]
            else:
                drop_idx = 0

            c = self.chunks.pop(drop_idx)
            cid = c.get("chunk_id")
            if cid in self._chunk_ids:
                self._chunk_ids.remove(cid)
            dropped.append(cid)

        if dropped:
            self.pruning_log["dropped"].extend(dropped)
        return dropped

    @staticmethod
    def _tokenize(text):
        text = (text or "").lower()
        return re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]", text)

    @classmethod
    def _infer_answer_type(cls, question):
        q = str(question or "").strip().lower()
        if not q:
            return "open_text"
        count_markers = ["how many", "number of", "count", "多少", "几个", "几种", "数量"]
        for marker in count_markers:
            if marker in q:
                return "count"
        paragraph_markers = ["paragraph", "段落", "第几段", "哪一段"]
        for marker in paragraph_markers:
            if marker in q:
                return "paragraph_id"
        entity_markers = ["who", "where", "when", "which", "what", "谁", "哪里", "哪位", "何时", "哪个"]
        if any([q.startswith(m) for m in entity_markers]) or any([m in q for m in entity_markers]):
            return "entity_short"
        return "open_text"

    @staticmethod
    def _normalize_numeric(text):
        value = str(text or "").strip()
        if not value:
            return ""
        value = value.replace(",", "")
        if value.endswith(".0"):
            value = value[:-2]
        return value

    @classmethod
    def _extract_number(cls, text):
        src = str(text or "")
        m = re.search(r"(?<![a-zA-Z0-9_])(-?\d+(?:[.,]\d+)?)", src)
        if not m:
            return ""
        return cls._normalize_numeric(m.group(1))

    @staticmethod
    def _extract_paragraph_id(text):
        src = str(text or "")
        patterns = [
            r"(?i)\bparagraph\s*(\d+)\b",
            r"(?i)\bpara\s*(\d+)\b",
            r"段落\s*(\d+)",
            r"第\s*(\d+)\s*段",
        ]
        for pat in patterns:
            m = re.search(pat, src)
            if m:
                return str(m.group(1))
        return ""

    @staticmethod
    def _extract_entity_short(text, max_chars=48):
        src = str(text or "").strip()
        if not src:
            return ""
        first = re.split(r"[\n。！？!?]", src)[0].strip()
        if not first:
            first = src
        first = first.strip(" \"'`:,;：；")
        if len(first) > int(max_chars):
            first = first[: int(max_chars)].rstrip(" ,:;：；")
        return first

    def _best_chunk_text(self, question):
        q_tokens = self._tokenize(question)
        best_text = self.chunks[0].get("text", "")
        best_score = -1
        for c in self.chunks:
            txt = c.get("text", "")
            low = txt.lower()
            score = 0
            for t in q_tokens:
                if t in low:
                    score += 1
            if score > best_score:
                best_score = score
                best_text = txt
        return str(best_text or "").strip()

    def best_answer_from_chunks(self, question, task=None, answer_type=None, max_chars=None):
        if not self.chunks:
            return "信息不足，无法确定答案。"
        task_name = str(task or "").strip().lower()
        kind = str(answer_type or "").strip().lower() or self._infer_answer_type(question)
        if max_chars is None:
            max_chars = 64 if task_name == "single_doc_qa" else 96
        max_chars = max(24, int(max_chars))

        best_text = self._best_chunk_text(question)
        extracted = ""

        if kind == "count":
            extracted = self._extract_number(best_text)
            if not extracted:
                for c in self.chunks:
                    extracted = self._extract_number(c.get("text", ""))
                    if extracted:
                        break
        elif kind == "paragraph_id":
            pid = self._extract_paragraph_id(best_text)
            if not pid:
                for c in self.chunks:
                    pid = self._extract_paragraph_id(c.get("text", ""))
                    if pid:
                        break
            if pid:
                if re.search(r"[\u4e00-\u9fff]", str(question or "")):
                    extracted = "段落{}".format(pid)
                else:
                    extracted = "Paragraph {}".format(pid)
        elif kind == "entity_short":
            extracted = self._extract_entity_short(best_text, max_chars=min(48, max_chars))

        fallback = best_text
        if len(fallback) > max_chars:
            fallback = fallback[:max_chars].rstrip(" ,:;：；")

        out = str(extracted or fallback).strip()
        if not out:
            return "信息不足，无法确定答案。"
        return out
