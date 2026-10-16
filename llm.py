
"""LifeLine - tiny Groq client using only the Python standard library.
 
Groq's API is OpenAI-compatible, so we just POST to /chat/completions.
Free keys: https://console.groq.com/keys  (put it in the GROQ_API_KEY variable).
 
If there is no key, or Groq is down or rate-limited, every function returns None
and the agent falls back to its built-in rules. The app keeps working offline,
which matters because emergency tools must never depend on a network call.
"""
import json
import os
import time
import urllib.error
import urllib.request
 
API_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/") + "/chat/completions"
 
# Groq's model catalogue changes often. Try the preferred model first, then fall
# back. Override with GROQ_MODEL="model1,model2" if a model is retired.
# (llama-3.3-70b-versatile and llama-3.1-8b-instant were retired on 16 Aug 2026.)
DEFAULT_MODELS = ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]
 
 
def models():
    raw = os.getenv("GROQ_MODEL", "")
    chosen = [m.strip() for m in raw.split(",") if m.strip()]
    return chosen or DEFAULT_MODELS
 
 
def enabled():
    return bool(os.getenv("GROQ_API_KEY"))
 
 
# After a failure we pause calls briefly instead of hammering a broken service.
_cooldown_until = 0.0
last_error = ""      # shown at /api/health?test=1 and printed in the terminal
 
 
def _fail(msg, pause):
    global _cooldown_until, last_error
    last_error = msg
    _cooldown_until = time.time() + pause
    print(f"[groq] {msg}")
 
 
def chat(messages, json_mode=False, max_tokens=300, timeout=15):
    """Return the model's reply text, or None if unavailable."""
    global _cooldown_until, last_error
    key = os.getenv("GROQ_API_KEY")
    if not key or time.time() < _cooldown_until:
        return None
 
    for model in models():
        body = {
            "model": model,
            "messages": messages,
            "temperature": 0,          # same input -> same output (safer, testable)
        }
        if model.startswith("openai/gpt-oss"):
            # gpt-oss is a "reasoning" model: it needs max_completion_tokens (not
            # max_tokens), and its hidden thinking counts toward the limit, so we
            # keep thinking short and add headroom so the real answer is not cut off.
            body["max_completion_tokens"] = max_tokens + 400
            body["reasoning_effort"] = "low"
            body["include_reasoning"] = False
        else:
            body["max_tokens"] = max_tokens
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        req = urllib.request.Request(
            API_URL,
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                     "User-Agent": "lifeline-first-aid/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.load(resp)
            text = (data["choices"][0]["message"].get("content") or "").strip()
            if text:
                return text
            last_error = f"empty reply from {model}"
            print(f"[groq] {last_error}")
            continue                                # try the next model
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode("utf-8", "replace")[:200]
            except Exception:
                detail = ""
            if e.code == 429:                       # rate limited: stop for a while
                _fail(f"HTTP 429 rate limited ({model}). {detail}", 20)
                return None
            if e.code in (400, 404):                # model retired/unknown: try the next one
                last_error = f"HTTP {e.code} for model {model}: {detail}"
                print(f"[groq] {last_error}")
                continue
            hint = " (is the key valid and copied in full?)" if e.code in (401, 403) else ""
            _fail(f"HTTP {e.code}{hint}: {detail}", 10)
            return None
        except Exception as e:
            _fail(f"{type(e).__name__}: {e}", 10)
            return None
    return None
 
 
def chat_json(messages, **kw):
    """Like chat() but parses a JSON object; returns dict or None."""
    text = chat(messages, json_mode=True, **kw)
    if not text:
        return None
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None
 
 
def test():
    """Live check used by /api/health?test=1. Returns {"ok", "model", "error"}."""
    global _cooldown_until
    if not enabled():
        return {"ok": False, "error": "GROQ_API_KEY is not set (is your file named exactly .env ?)"}
    _cooldown_until = 0.0
    reply = chat([{"role": "user", "content": "Reply with the single word OK."}], max_tokens=5)
    return {"ok": bool(reply), "reply": reply, "models": models(), "error": None if reply else last_error or "no reply"}

