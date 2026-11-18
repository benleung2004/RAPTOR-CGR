"""CS Textbook Tutor - web server.

    python web/server.py            # http://127.0.0.1:8000  (needs CHAT_PRIMARY_API_KEY in .env)
    python web/server.py --demo     # no API key: shows retrieved excerpts instead of an AI answer

POST /api/chat streams Server-Sent Events: sources -> delta* -> done | error.
"""

import argparse
import json
import os
import sys
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.responses import FileResponse, StreamingResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field, field_validator  # noqa: E402

STATIC = Path(__file__).parent / "static"
MAX_QUESTION_CHARS = 2000


class Message(BaseModel):
    role: str
    content: str = Field(max_length=8000)

    @field_validator("role")
    @classmethod
    def known_role(cls, v):
        if v not in ("user", "assistant"):
            raise ValueError("role must be user or assistant")
        return v


class RevalidatedStatic(StaticFiles):
    """Static files that browsers re-check on every load (ETag), so updates show up immediately."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    history: list[Message] = Field(default_factory=list, max_length=8)


class RateLimiter:
    """Sliding-window limits per client IP (in memory; fine for a single server process)."""

    def __init__(self, per_minute, per_day):
        self.per_minute, self.per_day = per_minute, per_day
        self.hits = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, client):
        now = time.time()
        with self._lock:
            q = self.hits[client]
            while q and now - q[0] > 86400:
                q.popleft()
            if len(q) >= self.per_day or sum(1 for t in q if now - t < 60) >= self.per_minute:
                return False
            q.append(now)
            return True


def create_app(engine, limiter=None, mode="live"):
    app = FastAPI(title="CS Textbook Tutor", docs_url=None, redoc_url=None)
    limiter = limiter or RateLimiter(int(os.getenv("CHAT_RATE_PER_MINUTE", 6)), int(os.getenv("CHAT_RATE_PER_DAY", 150)))

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/api/health")
    def health():
        return {"status": "ok", "mode": mode, "chunks": len(engine.index.chunks),
                "providers": [{"name": p.name, "model": p.model} for p in engine.providers]}

    @app.post("/api/chat")
    def chat(req: ChatRequest, request: Request):
        question = req.question.strip()
        if not question:
            raise HTTPException(422, "Question is empty.")
        client = request.headers.get("cf-connecting-ip") or (request.client.host if request.client else "?")
        if not limiter.check(client):
            raise HTTPException(429, "Too many questions - please wait a minute and try again.")

        def events():
            try:
                for kind, data in engine.answer(question, [m.model_dump() for m in req.history]):
                    yield f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
            except Exception as e:  # never leak internals to the browser
                print("chat error:", type(e).__name__, e)
                yield f"event: error\ndata: {json.dumps('Something went wrong. Please try again.')}\n\n"

        return StreamingResponse(events(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    app.mount("/static", RevalidatedStatic(directory=STATIC), name="static")
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--demo", action="store_true", help="run without an API key")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    from chat_engine import ChatEngine, DemoProvider, TextbookIndex, providers_from_env
    providers = [DemoProvider()] if args.demo else providers_from_env()
    if not providers:
        raise SystemExit("No CHAT_PRIMARY_API_KEY in .env - add one (see .env.example) or use --demo.")
    print("Loading textbook index...")
    engine = ChatEngine(TextbookIndex.load(), providers)
    print(f"Ready: http://{args.host}:{args.port}  ({', '.join(p.name for p in providers)})")

    import uvicorn
    uvicorn.run(create_app(engine, mode="demo" if args.demo else "live"), host=args.host, port=args.port,
                log_level="warning")


if __name__ == "__main__":
    main()
