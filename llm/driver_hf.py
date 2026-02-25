import re

from llm.driver_local import LocalLLMDriver


class HFLLMDriver(object):
    def __init__(self, cfg):
        self.cfg = cfg or {}
        runtime_cfg = self.cfg.get("runtime", {})
        self.run_mode = str(runtime_cfg.get("run_mode", "formal")).lower()
        runtime_seed = runtime_cfg.get("seed")
        self.runtime_seed = None
        if runtime_seed is not None:
            try:
                self.runtime_seed = int(runtime_seed)
            except Exception:
                self.runtime_seed = None
        self._fallback = LocalLLMDriver(cfg)
        self._pipe = None
        self._load_error = ""
        self._last_backend_mode = "unknown"
        self._last_error = ""
        self._try_load()

    def _try_load(self):
        model_name = self.cfg.get("model", {}).get("name_or_path", "Qwen/Qwen3-0.6B")
        try:
            from transformers import pipeline

            self._pipe = pipeline(
                "text-generation",
                model=model_name,
                device_map="auto",
            )
        except Exception as exc:
            self._pipe = None
            self._load_error = str(exc)
            self._last_error = self._load_error

    @property
    def backend_mode(self):
        return self._last_backend_mode

    @property
    def last_error(self):
        if self._last_error:
            return self._last_error
        return self._load_error

    def generate(
        self,
        prompt,
        system_prompt="",
        temperature=None,
        top_p=None,
        top_k=None,
        max_new_tokens=None,
        stop=None,
        expect_protocol=False,
    ):
        if self._pipe is None:
            if self.run_mode == "formal":
                raise RuntimeError("HF backend unavailable in formal mode: {}".format(self._load_error or "unknown error"))
            text = self._fallback.generate(
                prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                max_new_tokens=max_new_tokens,
                stop=stop,
                expect_protocol=expect_protocol,
            )
            self._last_backend_mode = self._fallback.backend_mode
            return text

        text = prompt if not system_prompt else system_prompt + "\n\n" + prompt
        decoding_cfg = self.cfg.get("model", {}).get("decoding", {})
        if temperature is None:
            temperature = decoding_cfg.get("temperature", 0.2)
        if top_p is None:
            top_p = decoding_cfg.get("top_p", 1.0)
        if top_k is None:
            top_k = decoding_cfg.get("top_k", 0)
        if max_new_tokens is None:
            max_new_tokens = decoding_cfg.get("max_new_tokens", 256)

        try:
            temp = float(temperature)
            do_sample = temp > 0.0
            kwargs = {
                "max_new_tokens": int(max_new_tokens),
                "do_sample": bool(do_sample),
            }
            if do_sample:
                kwargs["temperature"] = temp
                kwargs["top_p"] = float(top_p) if top_p is not None else 1.0
                if top_k is not None:
                    kwargs["top_k"] = max(0, int(top_k))
            if stop:
                kwargs["eos_token_id"] = None
            if self.runtime_seed is not None:
                try:
                    import torch

                    torch.manual_seed(int(self.runtime_seed))
                    if torch.cuda.is_available():
                        torch.cuda.manual_seed_all(int(self.runtime_seed))
                except Exception:
                    pass
            out = self._pipe(
                text,
                **kwargs,
            )
            if not out:
                raise RuntimeError("empty generation")
            gen = out[0].get("generated_text", "")
            if gen.startswith(text):
                gen = gen[len(text) :]
            gen = gen.strip()
            if expect_protocol and gen:
                m = re.search(r"<\s*(search|final)\s*>(.*?)<\s*/\s*\1\s*>", gen, flags=re.I | re.S)
                if m:
                    tag = m.group(1).lower()
                    body = (m.group(2) or "").strip()[:512]
                    gen = "<{}>{}</{}>".format(tag, body, tag)
            if gen:
                self._last_backend_mode = "real"
                return gen
            raise RuntimeError("empty generation text")
        except Exception as exc:
            self._last_error = str(exc)
            if self.run_mode == "formal":
                raise RuntimeError("HF inference failed in formal mode: {}".format(self._last_error))
            fb_text = self._fallback.generate(
                prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                max_new_tokens=max_new_tokens,
                stop=stop,
                expect_protocol=expect_protocol,
            )
            self._last_backend_mode = self._fallback.backend_mode
            return fb_text
