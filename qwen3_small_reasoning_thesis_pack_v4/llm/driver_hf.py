from llm.driver_local import LocalLLMDriver


class HFLLMDriver(object):
    def __init__(self, cfg):
        self.cfg = cfg or {}
        self._fallback = LocalLLMDriver(cfg)
        self._pipe = None
        self._load_error = ""
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

    def generate(
        self,
        prompt,
        system_prompt="",
        temperature=None,
        max_new_tokens=None,
        expect_protocol=False,
    ):
        if self._pipe is None:
            return self._fallback.generate(
                prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_new_tokens=max_new_tokens,
                expect_protocol=expect_protocol,
            )

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
            return gen or self._fallback.generate(
                prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_new_tokens=max_new_tokens,
                expect_protocol=expect_protocol,
            )
        except Exception:
            return self._fallback.generate(
                prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_new_tokens=max_new_tokens,
                expect_protocol=expect_protocol,
            )
