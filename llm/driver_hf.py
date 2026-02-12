from llm.driver_local import LocalLLMDriver


class HFLLMDriver(object):
    def __init__(self, cfg):
        self.cfg = cfg or {}
        runtime_cfg = self.cfg.get("runtime", {})
        self.run_mode = str(runtime_cfg.get("run_mode", "formal")).lower()
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
        max_new_tokens=None,
        expect_protocol=False,
    ):
        if self._pipe is None:
            if self.run_mode == "formal":
                raise RuntimeError("HF backend unavailable in formal mode: {}".format(self._load_error or "unknown error"))
            text = self._fallback.generate(
                prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_new_tokens=max_new_tokens,
                expect_protocol=expect_protocol,
            )
            self._last_backend_mode = self._fallback.backend_mode
            return text

        text = prompt if not system_prompt else system_prompt + "\n\n" + prompt
        if temperature is None:
            temperature = self.cfg.get("model", {}).get("decoding", {}).get("temperature", 0.2)
        if max_new_tokens is None:
            max_new_tokens = self.cfg.get("model", {}).get("decoding", {}).get("max_new_tokens", 256)

        try:
            out = self._pipe(
                text,
                max_new_tokens=int(max_new_tokens),
                temperature=float(temperature),
                do_sample=True,
            )
            if not out:
                raise RuntimeError("empty generation")
            gen = out[0].get("generated_text", "")
            if gen.startswith(text):
                gen = gen[len(text) :]
            gen = gen.strip()
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
                max_new_tokens=max_new_tokens,
                expect_protocol=expect_protocol,
            )
            self._last_backend_mode = self._fallback.backend_mode
            return fb_text
