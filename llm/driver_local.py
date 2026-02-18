import json
import re

import requests


class LocalLLMDriver(object):
    def __init__(self, cfg):
        self.cfg = cfg or {}
        model_cfg = self.cfg.get("model", {})
        local_cfg = self.cfg.get("local_backend", {})
        fb_cfg = self.cfg.get("fallback", {})
        runtime_cfg = self.cfg.get("runtime", {})

        self.model = model_cfg.get("name_or_path", "qwen3:8b")
        self.base_url = local_cfg.get("base_url", "http://localhost:11434/v1")
        self.timeout = int(local_cfg.get("request_timeout_s", 120))
        self.run_mode = str(runtime_cfg.get("run_mode", "formal")).lower()
        runtime_seed = runtime_cfg.get("seed")
        self.runtime_seed = None
        if runtime_seed is not None:
            try:
                self.runtime_seed = int(runtime_seed)
            except Exception:
                self.runtime_seed = None
        self.fallback_enable = bool(
            fb_cfg.get("enable", local_cfg.get("use_mock_if_unavailable", True))
        )
        self.fallback_mode = fb_cfg.get("mode", "heuristic")
        self._last_error = ""
        self._last_backend_mode = "unknown"

    @property
    def last_error(self):
        return self._last_error

    @property
    def backend_mode(self):
        return self._last_backend_mode

    @property
    def mock_allowed(self):
        return self.run_mode == "smoke" and self.fallback_enable

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
            expect_protocol=expect_protocol,
        )
        if content is not None:
            self._last_backend_mode = "real"
            return content

        if not self.mock_allowed:
            if self.run_mode == "formal":
                raise RuntimeError(
                    "Local backend unavailable in formal mode: {}".format(self._last_error or "unknown error")
                )
            raise RuntimeError(
                "Local backend unavailable and fallback disabled: {}".format(self._last_error or "unknown error")
            )

        self._last_backend_mode = "mock"
        return self._mock_generate(prompt, expect_protocol=expect_protocol)

    @staticmethod
    def _as_text(value):
        if isinstance(value, list):
            out = []
            for item in value:
                if isinstance(item, dict):
                    txt = item.get("text", "")
                    if txt:
                        out.append(str(txt))
                elif isinstance(item, str):
                    out.append(item)
            return "\n".join(out).strip()
        if value is None:
            return ""
        return str(value).strip()

    def _apply_soft_switch(self, prompt, expect_protocol=False):
        model_cfg = self.cfg.get("model", {})
        thinking_cfg = model_cfg.get("thinking", {}) or {}
        soft_cfg = thinking_cfg.get("soft_switch", {}) or {}
        enable_think = bool(thinking_cfg.get("enable", False))
        think_tag = str(soft_cfg.get("think", "") or "").strip()
        no_think_tag = str(soft_cfg.get("no_think", "") or "").strip()
        if expect_protocol and no_think_tag:
            selected_tag = no_think_tag
        else:
            selected_tag = think_tag if enable_think else no_think_tag
        if not selected_tag:
            return prompt
        prompt = prompt or ""
        stripped = prompt.lstrip()
        if think_tag and stripped.startswith(think_tag):
            return prompt
        if no_think_tag and stripped.startswith(no_think_tag):
            return prompt
        return "{}\n{}".format(selected_tag, prompt)

    def _extract_primary_text(self, message):
        if not isinstance(message, dict):
            return ""
        return self._as_text(message.get("content", ""))

    def _extract_reasoning_text(self, message):
        if not isinstance(message, dict):
            return ""
        for key in ["reasoning", "reasoning_content", "thinking", "thought"]:
            value = self._as_text(message.get(key, ""))
            if value:
                return value
        return ""

    def _extract_from_choice(self, choice):
        if not isinstance(choice, dict):
            return "", "", ""
        message = choice.get("message", {})
        content = self._extract_primary_text(message)
        reasoning = self._extract_reasoning_text(message)
        finish_reason = str(choice.get("finish_reason", "") or "")
        return content, reasoning, finish_reason

    def _request_chat_once(self, endpoint, payload):
        resp = requests.post(endpoint, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            return "", "", ""
        return self._extract_from_choice(choices[0])

    @staticmethod
    def _reasoning_fallback(reasoning_text, expect_protocol):
        text = (reasoning_text or "").strip()
        if not text:
            return None
        if expect_protocol:
            m = re.search(r"<\s*(search|final)\s*>.*?<\s*/\s*\1\s*>", text, flags=re.I | re.S)
            if m:
                return m.group(0).strip()
            lines = [x.strip() for x in text.splitlines() if x.strip()]
            tail = lines[-1] if lines else text
            return "<final>{}</final>".format(tail)
        lines = [x.strip() for x in text.splitlines() if x.strip()]
        return (lines[-1] if lines else text).strip() or None

    def _generate_remote(self, prompt, system_prompt, temperature, max_new_tokens, expect_protocol=False):
        endpoint = self.base_url.rstrip("/") + "/chat/completions"
        user_prompt = self._apply_soft_switch(prompt, expect_protocol=expect_protocol)
        payload = {
            "model": self.model,
            "messages": [],
            "temperature": float(temperature),
            "max_tokens": int(max_new_tokens),
        }
        if self.runtime_seed is not None:
            payload["seed"] = int(self.runtime_seed)
        if system_prompt:
            payload["messages"].append({"role": "system", "content": system_prompt})
        payload["messages"].append({"role": "user", "content": user_prompt})

        try:
            content, reasoning, finish_reason = self._request_chat_once(endpoint, payload)
            if content:
                return content

            retry_max_tokens = min(max(512, int(max_new_tokens) * 2), 2048)
            if finish_reason == "length" and retry_max_tokens > int(max_new_tokens):
                retry_payload = dict(payload)
                retry_payload["max_tokens"] = int(retry_max_tokens)
                content2, reasoning2, finish_reason2 = self._request_chat_once(endpoint, retry_payload)
                if content2:
                    return content2
                if reasoning2:
                    reasoning = reasoning2
                finish_reason = finish_reason2 or finish_reason

            fallback = self._reasoning_fallback(reasoning, expect_protocol=expect_protocol)
            if fallback:
                return fallback

            self._last_error = "empty content from local backend (finish_reason={})".format(finish_reason or "unknown")
            return None
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
