"""
LifeLine web server.   Run:  python server.py     then open http://localhost:8000

Endpoints are plain `def` (not async) on purpose: FastAPI runs them in a thread pool,
so a slow Groq call never blocks other users.
"""
import os
import time
from collections import defaultdict, deque
from pathlib import Path
from threading import Lock
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import llm
from agent import Agent, urgent_topic
from knowledge import CATEGORIES, EMERGENCY_NUMBERS, TOPICS, public_topic

BASE = Path(__file__).parent
STATIC = BASE / "static"

# Optional: read GROQ_API_KEY from a .env file next to this script (no extra library needed).
env_file = BASE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

app = FastAPI(title="LifeLine First Aid Assistant", docs_url="/api/docs", redoc_url=None)

# ------------------------------------------------------------------ session store
SESSIONS: dict[str, Agent] = {}
SESSION_SEEN: dict[str, float] = {}
MAX_SESSIONS = 500
SESSION_TTL = 3 * 3600
_lock = Lock()


def get_agent(session_id: Optional[str]) -> Agent:
    """Find the user's agent, or make a new one."""
    now = time.time()
    with _lock:
        for sid in [s for s, t in SESSION_SEEN.items() if now - t > SESSION_TTL]:
            SESSIONS.pop(sid, None)
            SESSION_SEEN.pop(sid, None)
        if len(SESSIONS) >= MAX_SESSIONS:                      # drop the oldest
            oldest = min(SESSION_SEEN, key=SESSION_SEEN.get)
            SESSIONS.pop(oldest, None)
            SESSION_SEEN.pop(oldest, None)
        if session_id and session_id in SESSIONS:
            agent = SESSIONS[session_id]
        else:
            agent = Agent()
            SESSIONS[agent.session_id] = agent
        SESSION_SEEN[agent.session_id] = now
        return agent


# ------------------------------------------------------------------ rate limit (protects the free Groq quota)
_hits: dict[str, deque] = defaultdict(deque)


def rate_limit(request: Request, limit: int = 20, window: int = 60):
    ip = request.client.host if request.client else "unknown"
    q = _hits[ip]
    now = time.time()
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(429, "Too many requests. Please wait a moment. In an emergency call 112 now.")
    q.append(now)


# ------------------------------------------------------------------ request models
class SessionBody(BaseModel):
    session_id: Optional[str] = None


class MessageBody(SessionBody):
    text: str = Field(min_length=1, max_length=600)


class StartBody(SessionBody):
    topic: str
    infant: bool = False


class AnswerBody(SessionBody):
    yes: bool


class AskBody(SessionBody):
    question: str = Field(min_length=1, max_length=400)


# ------------------------------------------------------------------ API
import photo_api  # photo analysis add-on
photo_api.setup(app, get_agent, rate_limit)


@app.get("/api/config")
def config():
    return {
        "numbers": EMERGENCY_NUMBERS,
        "categories": [{"id": i, "label": l} for i, l in CATEGORIES],
        "topics": [public_topic(t) for t in TOPICS],
        "ai": {"enabled": llm.enabled(), "models": llm.models() if llm.enabled() else []},
    }


@app.post("/api/message")
def message(body: MessageBody, request: Request):
    rate_limit(request)
    agent = get_agent(body.session_id)
    agent.perceive(body.text)
    return agent.view()


@app.post("/api/start")
def start(body: StartBody):
    if body.topic not in TOPICS:
        raise HTTPException(404, "Unknown topic")
    agent = get_agent(body.session_id)
    agent.start(body.topic, body.infant)
    return agent.view()


@app.post("/api/triage")
def triage(body: AnswerBody):
    agent = get_agent(body.session_id)
    if agent.choose_action()["kind"] == "triage":
        agent.answer_triage(body.yes)
    return agent.view()


@app.post("/api/checkin")
def checkin(body: AnswerBody):
    agent = get_agent(body.session_id)
    if agent.choose_action()["kind"] == "checkin":
        agent.answer_checkin(body.yes)
    return agent.view()


@app.post("/api/next")
def next_step(body: SessionBody):
    agent = get_agent(body.session_id)
    if agent.choose_action()["kind"] == "step":
        agent.next_step()
    return agent.view()


@app.post("/api/back")
def back(body: SessionBody):
    agent = get_agent(body.session_id)
    agent.prev_step()
    return agent.view()


@app.post("/api/alt")
def alt(body: SessionBody):
    agent = get_agent(body.session_id)
    agent.take_alt()
    return agent.view()


@app.post("/api/reset")
def reset(body: SessionBody):
    agent = get_agent(body.session_id)
    agent.reset()
    return agent.view()


@app.post("/api/ask")
def ask(body: AskBody, request: Request):
    rate_limit(request)
    agent = get_agent(body.session_id)
    # A new emergency inside a question ("he stopped breathing!") re-plans immediately.
    urgent = urgent_topic(body.question)
    if urgent and agent.topic != urgent:
        agent.start(urgent, via="emergency-pattern")
        agent.notice = "Switched to CPR because you said the person is not breathing."
        return {"answer": "Switching to CPR now. Follow the steps on screen and call 112 / 108.",
                "via": "rules", "view": agent.view()}
    out = agent.ask(body.question)
    return {**out, "view": agent.view()}


@app.get("/api/health")
def health(request: Request, test: int = 0):
    """Open /api/health?test=1 in the browser to check the Groq connection and see the exact error."""
    out = {"ok": True, "ai_key_found": llm.enabled(), "topics": len(TOPICS)}
    if test:
        rate_limit(request, limit=6)
        out["groq_test"] = llm.test()
    return out


# ------------------------------------------------------------------ security headers + static site
@app.middleware("http")
async def headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Permissions-Policy"] = "microphone=(self), geolocation=(self)"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "connect-src 'self'; frame-ancestors 'none'")
    if request.url.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/sw.js")
def service_worker():
    # Served from the root so it can control the whole site (makes the app installable/offline-friendly).
    return FileResponse(STATIC / "sw.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})


app.mount("/static", StaticFiles(directory=STATIC), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    print(f"\n  LifeLine running at http://localhost:{port}")
    print("  AI mode:", "Groq connected" if llm.enabled() else "offline (no GROQ_API_KEY): rules only", "\n")
    uvicorn.run(app, host=os.getenv("HOST", "127.0.0.1"), port=port)
