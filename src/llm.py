"""Thin, thread-safe wrapper around an OpenAI-compatible chat API with retries and token accounting."""

import random
import threading
import time

from common import model_config


class LLM:
    def __init__(self, role="answer", client=None, model=None, extra_body=None):
        cfg = model_config(role)
        if client is None:
            if not cfg["api_key"]:
                raise SystemExit("No API key: copy .env.example to .env and set LLM_API_KEY "
                                 "(and optionally JUDGE_*).")
            from openai import OpenAI
            client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"], max_retries=0, timeout=120)
        self.client = client
        self.model = model or cfg["model"]
        self.extra_body = extra_body if extra_body is not None else (cfg["extra_body"] if client is None else None)
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.calls = 0
        self._lock = threading.Lock()

    def chat(self, messages, temperature=0.0, max_tokens=None, retries=6):
        """Return (text, usage dict). Retries with exponential backoff on any API error."""
        kwargs = {"max_tokens": max_tokens} if max_tokens else {}
        if self.extra_body:
            kwargs["extra_body"] = self.extra_body
        for attempt in range(retries):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model, messages=messages, temperature=temperature, **kwargs)
                text = (resp.choices[0].message.content or "").strip()
                usage = getattr(resp, "usage", None)
                u = {"prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                     "completion_tokens": getattr(usage, "completion_tokens", 0) or 0}
                with self._lock:
                    self.calls += 1
                    self.prompt_tokens += u["prompt_tokens"]
                    self.completion_tokens += u["completion_tokens"]
                return text, u
            except Exception as e:  # rate limits, timeouts, 5xx ...
                if attempt == retries - 1:
                    raise
                wait = min(60, 2 ** attempt) + random.random()
                print(f"  API error ({type(e).__name__}: {str(e)[:120]}), retry in {wait:.0f}s")
                time.sleep(wait)

    def usage_summary(self):
        return {"model": self.model, "calls": self.calls,
                "prompt_tokens": self.prompt_tokens, "completion_tokens": self.completion_tokens}
