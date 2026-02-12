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

    def best_answer_from_chunks(self, question):
        if not self.chunks:
            return "信息不足，无法确定答案。"
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
        best_text = best_text.strip()
        if len(best_text) > 220:
            best_text = best_text[:220]
        return best_text or "信息不足，无法确定答案。"
