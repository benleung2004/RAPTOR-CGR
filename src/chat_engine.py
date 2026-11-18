"""Answer engine for the web tutor: textbook retrieval + one grounded LLM call, streamed.

One request = embed the question locally (~20 ms) + search the textbook index (~20 ms) + a single
streamed LLM call. No web search and no multi-step agent loop, which keeps answers fast and
grounded in the 20 GraphRAG-Bench textbooks.

Providers are any OpenAI-compatible endpoints configured in .env (CHAT_PRIMARY_*, CHAT_FALLBACK_*).
If the primary fails before sending any text (rate limit, outage), the fallback is used.
"""

import json
import os
import re
import threading
import time
from collections import OrderedDict
from pathlib import Path

import numpy as np

from common import ROOT, load_env

WEB_INDEX_DIR = ROOT / "data" / "web_index"

SYSTEM_PROMPT = """You are a careful computer science tutor for university students.
You answer using the numbered textbook excerpts provided with each question.

How to answer:
1. Start with a short, direct answer (1-3 sentences).
2. Then explain step by step, grounded in the excerpts. Cite the excerpts you use like [1] or [2][3].
3. Algorithms, computations and maths: give numbered steps, then pseudocode in a ```text code block
   (or Python in a ```python block when code is clearer), and work through a small example when it helps.
   Write maths in LaTeX: $...$ inline and $$...$$ for display.
4. If the excerpts do not cover the question, say so in one sentence, then answer from general
   computer science knowledge without citations. Never invent citations or facts about the excerpts.
5. Be concise and precise. Use Markdown headings and lists only when they help.

Language: reply in the language of the question. For Chinese questions use Traditional Chinese and
keep technical terms in English in brackets the first time, e.g. 二元搜尋樹 (binary search tree).
Only discuss computer science; politely decline unrelated requests."""


# ── Retrieval ────────────────────────────────────────────────────────────────
class TextbookIndex:
    """Cosine search over pre-normalised chunk embeddings (multilingual-e5-small)."""

    def __init__(self, vectors, chunks, embed_query):
        self.vectors = np.asarray(vectors, dtype=np.float32)
        self.chunks = chunks
        self.embed_query = embed_query
        self._lock = threading.Lock()

    @classmethod
    def load(cls, index_dir=WEB_INDEX_DIR):
        index_dir = Path(index_dir)
        if not (index_dir / "embeddings.npy").exists():
            raise SystemExit("Web index not found - run: python src/build_web_index.py")
        meta = json.loads((index_dir / "meta.json").read_text(encoding="utf-8"))
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(meta["embedding_model"])
        chunks = [json.loads(l) for l in (index_dir / "chunks.jsonl").read_text(encoding="utf-8").splitlines()]
        return cls(np.load(index_dir / "embeddings.npy"), chunks,
                   lambda text: model.encode([f"query: {text}"], normalize_embeddings=True)[0])

    def search(self, query, top_k=6):
        with self._lock:                                   # the embedding model is not thread-safe
            q = np.asarray(self.embed_query(query), dtype=np.float32)
        scores = self.vectors @ q
        best = np.argpartition(-scores, min(top_k, len(scores) - 1))[:top_k]
        best = best[np.argsort(-scores[best])]
        return [{**self.chunks[i], "score": round(float(scores[i]), 4)} for i in best]


def retrieval_query(question, history):
    """Short follow-ups ("why?", "give an example") are searched together with the previous question."""
    prev = [m["content"] for m in history if m.get("role") == "user"]
    if prev and len(re.findall(r"\w+", question)) <= 6:
        return f"{prev[-1]}\n{question}"
    return question


def build_messages(question, sources, history):
    excerpts = "\n\n".join(
        f"[{n}] {s['title']} — {s['section'] or 'excerpt'}\n{s['text']}" for n, s in enumerate(sources, 1))
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in history[-4:]:                                  # last two exchanges for follow-ups
        messages.append({"role": m["role"], "content": m["content"][:3000]})
    messages.append({"role": "user", "content": f"Textbook excerpts:\n\n{excerpts}\n\nQuestion: {question}"})
    return messages


# ── LLM providers ────────────────────────────────────────────────────────────
class Provider:
    def __init__(self, name, base_url, api_key, model, reasoning_effort=None, client=None):
        self.name, self.model, self.reasoning_effort = name, model, reasoning_effort
        if client is None:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url=base_url, max_retries=0, timeout=60)
        self.client = client

    def stream(self, messages, max_tokens=1200):
        kwargs = {"extra_body": {"reasoning_effort": self.reasoning_effort}} if self.reasoning_effort else {}
        resp = self.client.chat.completions.create(model=self.model, messages=messages, temperature=0.2,
                                                   max_tokens=max_tokens, stream=True, **kwargs)
        for chunk in resp:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


def providers_from_env():
    load_env()
    found = []
    for slot, defaults in (("PRIMARY", ("groq", "https://api.groq.com/openai/v1", "openai/gpt-oss-120b", "low")),
                           ("FALLBACK", ("deepseek", "https://api.deepseek.com", "deepseek-flash", ""))):
        key = os.getenv(f"CHAT_{slot}_API_KEY")
        if key:
            found.append(Provider(os.getenv(f"CHAT_{slot}_NAME", defaults[0]),
                                  os.getenv(f"CHAT_{slot}_BASE_URL", defaults[1]), key,
                                  os.getenv(f"CHAT_{slot}_MODEL", defaults[2]),
                                  os.getenv(f"CHAT_{slot}_REASONING_EFFORT", defaults[3]) or None))
    return found


class DemoProvider:
    """Offline stand-in (no API key): shows the retrieved excerpts so the UI can be tried."""
    name, model = "demo", "offline-demo"

    def __init__(self):
        self.last_sources = []

    def stream(self, messages, max_tokens=None):
        text = ("**Demo mode** – no LLM is configured, so this shows what the tutor would read before answering.\n\n"
                "Most relevant textbook excerpts: " + " ".join(f"[{i}]" for i in range(1, 4)) +
                "\n\nExample of the maths and code rendering:\n\n$$T(n) = 2T(n/2) + O(n) = O(n \\log n)$$\n\n"
                "```text\nMERGE-SORT(A, p, r)\n  if p < r\n    q = floor((p + r) / 2)\n    MERGE-SORT(A, p, q)\n"
                "    MERGE-SORT(A, q + 1, r)\n    MERGE(A, p, q, r)\n```\n\n"
                "Add `CHAT_PRIMARY_API_KEY` to `.env` and restart to get real answers.")
        for word in re.findall(r"\S+\s*", text):
            time.sleep(0.01)
            yield word


# ── Engine ───────────────────────────────────────────────────────────────────
class ChatEngine:
    def __init__(self, index, providers, top_k=6, cache_size=256):
        if not providers:
            raise ValueError("at least one provider is required")
        self.index, self.providers, self.top_k = index, providers, top_k
        self.cache = OrderedDict()
        self.cache_size = cache_size
        self._cache_lock = threading.Lock()

    def answer(self, question, history=()):
        """Yield events: ('sources', [...]), ('delta', str)*, ('done', stats) or ('error', message)."""
        history = list(history)
        started = time.perf_counter()
        key = re.sub(r"\s+", " ", question.strip().lower()) if not history else None
        with self._cache_lock:
            cached = self.cache.get(key) if key else None
            if cached:
                self.cache.move_to_end(key)
        if cached:
            yield "sources", cached["sources"]
            yield "delta", cached["answer"]
            yield "done", {**cached["stats"], "cached": True, "total_ms": round((time.perf_counter() - started) * 1000)}
            return

        sources = self.index.search(retrieval_query(question, history), self.top_k)
        retrieval_ms = round((time.perf_counter() - started) * 1000)
        public_sources = [{k: s[k] for k in ("title", "section", "text", "score", "book")} for s in sources]
        yield "sources", public_sources
        messages = build_messages(question, sources, history)

        errors = []
        for provider in self.providers:
            parts, first_token_ms = [], None
            try:
                for piece in provider.stream(messages):
                    if first_token_ms is None:
                        first_token_ms = round((time.perf_counter() - started) * 1000)
                    parts.append(piece)
                    yield "delta", piece
            except Exception as e:
                errors.append(f"{provider.name}: {type(e).__name__}")
                if parts:                       # already streaming: cannot switch provider mid-answer
                    yield "error", "The answer was interrupted. Please try again."
                    return
                continue
            if not parts:
                errors.append(f"{provider.name}: empty answer")
                continue
            stats = {"provider": provider.name, "model": provider.model, "retrieval_ms": retrieval_ms,
                     "first_token_ms": first_token_ms,
                     "total_ms": round((time.perf_counter() - started) * 1000), "cached": False}
            if key:
                with self._cache_lock:
                    self.cache[key] = {"sources": public_sources, "answer": "".join(parts), "stats": stats}
                    while len(self.cache) > self.cache_size:
                        self.cache.popitem(last=False)
            yield "done", stats
            return
        yield "error", "All AI providers are busy or unavailable right now. Please try again in a minute."
        print("chat providers failed:", "; ".join(errors))
