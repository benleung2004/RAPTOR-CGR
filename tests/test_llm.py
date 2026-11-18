"""LLM wrapper used by the research pipeline: provider options reach the API call."""

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import common  # noqa: E402
from llm import LLM  # noqa: E402


class FakeClient:
    def __init__(self):
        self.kwargs = None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.kwargs = kwargs
        msg = SimpleNamespace(content=" OK ")
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=None)


class ExtraBody(unittest.TestCase):
    def setUp(self):
        self.saved = {k: os.environ.pop(k) for k in list(os.environ) if k.endswith("_EXTRA_BODY")}

    def tearDown(self):
        for k in [k for k in os.environ if k.endswith("_EXTRA_BODY")]:
            del os.environ[k]
        os.environ.update(self.saved)

    def test_deepseek_thinking_disabled_by_default(self):
        self.assertEqual(common.extra_body_for("LLM", "https://api.deepseek.com"), {"thinking": {"type": "disabled"}})
        self.assertIsNone(common.extra_body_for("LLM", "https://openrouter.ai/api/v1"))
        os.environ["JUDGE_EXTRA_BODY"] = '{"reasoning_effort": "low"}'
        self.assertEqual(common.extra_body_for("JUDGE", "https://api.deepseek.com"), {"reasoning_effort": "low"})

    def test_llm_sends_extra_body_and_strips_text(self):
        client = FakeClient()
        llm = LLM(client=client, model="m", extra_body={"thinking": {"type": "disabled"}})
        text, _ = llm.chat([{"role": "user", "content": "hi"}], max_tokens=100)
        self.assertEqual(text, "OK")
        self.assertEqual(client.kwargs["extra_body"], {"thinking": {"type": "disabled"}})
        self.assertEqual(client.kwargs["max_tokens"], 100)

    def test_no_extra_body_for_injected_test_clients(self):
        client = FakeClient()
        LLM(client=client, model="m").chat([{"role": "user", "content": "hi"}])
        self.assertNotIn("extra_body", client.kwargs)


if __name__ == "__main__":
    unittest.main()
