import json
import re

import requests


class LocalLLMDriver(object):
    def __init__(self, cfg):
        self.cfg = cfg or {}
        model_cfg = self.cfg.get("model", {})
        local_cfg = self.cfg.get("local_backend", {})
        fb_cfg = self.cfg.get("fallback", {})

        self.model = model_cfg.get("name_or_path", "qwen3:8b")
        self.base_url = local_cfg.get("base_url", "http://localhost:11434/v1")
        self.timeout = int(local_cfg.get("request_timeout_s", 120))
        self.fallback_enable = bool(
            fb_cfg.get("enable", local_cfg.get("use_mock_if_unavailable", True))
        )
        self.fallback_mode = fb_cfg.get("mode", "heuristic")
        self._last_error = ""

    @property
    def last_error(self):
        return self._last_error

    def generate(
        self,
        prompt,
        system_prompt="",
        temperature=None,
        max_new_tokens=None,
        expect_protocol=False,
    ):
        if temperature is None:
            temperature = self.cfg.get("model", {}).get("decoding", {}).get("temperature", 0.2)
        if max_new_tokens is None:
            max_new_tokens = self.cfg.get("model", {}).get("decoding", {}).get("max_new_tokens", 256)

        content = self._generate_remote(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_new_tokens=max_new_tokens,
        )
        if content is not None:
            return content

        if not self.fallback_enable:
            raise RuntimeError("Local backend unavailable and fallback disabled: {}".format(self._last_error))

        return self._mock_generate(prompt, expect_protocol=expect_protocol)

    def _generate_remote(self, prompt, system_prompt, temperature, max_new_tokens):
        endpoint = self.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.model,
            "messages": [],
            "temperature": float(temperature),
            "max_tokens": int(max_new_tokens),
        }
        if system_prompt:
            payload["messages"].append({"role": "system", "content": system_prompt})
        payload["messages"].append({"role": "user", "content": prompt})

        try:
            resp = requests.post(endpoint, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                return None
            msg = choices[0].get("message", {})
            text = msg.get("content", "")
            if isinstance(text, list):
                text = "\n".join([x.get("text", "") for x in text if isinstance(x, dict)])
            text = (text or "").strip()
            return text or None
        except Exception as exc:
            self._last_error = str(exc)
            return None

    @staticmethod
    def _extract_between(prompt, start_tag, end_tag):
        s = prompt.find(start_tag)
        if s < 0:
            return ""
        s += len(start_tag)
        e = prompt.find(end_tag, s)
        if e < 0:
            return prompt[s:].strip()
        return prompt[s:e].strip()

    @staticmethod
    def _tokenize(text):
        text = (text or "").lower()
        parts = re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]", text)
        stop = set(["的", "了", "是", "在", "和", "与", "请", "根据", "只", "回答", "what", "is", "the", "a", "an"])
        return [p for p in parts if p not in stop and len(p) >= 1]

    def _best_sentence(self, question, context):
        q_tokens = self._tokenize(question)
        if not context:
            return ""
        sentence_list = []
        for raw in re.split(r"[\n。！？!?]", context):
            s = raw.strip()
            if s:
                sentence_list.append(s)
        if not sentence_list:
            return context[:160]
        best = sentence_list[0]
        best_score = -1.0
        for s in sentence_list:
            score = 0
            lower = s.lower()
            for t in q_tokens:
                if t in lower:
                    score += 1
            if score > best_score:
                best_score = score
                best = s
        return best.strip()

    def _search_keyword(self, question):
        tokens = self._tokenize(question)
        if not tokens:
            return "关键信息"
        return " ".join(tokens[:4])

    def _mock_generate(self, prompt, expect_protocol=False):
        question = self._extract_between(prompt, "[QUESTION]", "[/QUESTION]")
        evidence = self._extract_between(prompt, "[EVIDENCE]", "[/EVIDENCE]")
        step_str = self._extract_between(prompt, "[STEP]", "[/STEP]")
        max_step_str = self._extract_between(prompt, "[MAX_STEPS]", "[/MAX_STEPS]")

        if not question:
            question = self._extract_between(prompt, "Question:", "Context:")
        if not evidence:
            evidence = self._extract_between(prompt, "Context:", "请输出")

        try:
            step = int(step_str) if step_str else 1
        except Exception:
            step = 1
        try:
            max_steps = int(max_step_str) if max_step_str else 4
        except Exception:
            max_steps = 4

        answer = self._best_sentence(question, evidence)
        if not answer:
            answer = "暂时没有足够信息。"

        if not expect_protocol:
            return answer

        has_repair = "[REPAIR_OUTPUT]" in prompt
        if has_repair:
            return "<final>{}</final>".format(answer)

        if (not evidence or len(evidence) < 24) and step < max_steps:
            return "<search>{}</search>".format(self._search_keyword(question))

        q_tokens = self._tokenize(question)
        overlap = 0
        lower_e = evidence.lower()
        for t in q_tokens:
            if t in lower_e:
                overlap += 1

        if overlap < 2 and step < max_steps:
            return "<search>{}</search>".format(self._search_keyword(question))

        return "<final>{}</final>".format(answer)
