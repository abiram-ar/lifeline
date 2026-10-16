"""
LifeLine photo add-on: the web endpoint.  Connected to server.py by two lines (apply_addon.py adds them):

    import photo_api
    photo_api.setup(app, get_agent, rate_limit)
"""
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

import integration  # noqa: F401  (upgrades the Agent: photo answers + emergency interrupt)
import trauma  # noqa: F401  (importing registers the "Road crash / serious fall" protocol)
import vision
from knowledge import TOPICS

router = APIRouter()
ALLOWED_PREFIXES = ("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,")
CAVEAT = ("I'm describing only what is visible. A photo can't show a spine injury, internal bleeding or "
          "how badly someone is hurt. If in doubt, call 112 / 108.")


class PhotoBody(BaseModel):
    session_id: Optional[str] = None
    image: str = Field(max_length=2_200_000)      # about 1.6 MB of image after base64
    note: str = Field("", max_length=300)


def setup(app, get_agent, rate_limit):
    """Attach the photo routes to the main app and borrow its session store and rate limiter."""

    @app.post("/api/photo")
    def photo(body: PhotoBody, request: Request):
        rate_limit(request, limit=6, window=60)              # photos are slow and use the free quota
        if not body.image.startswith(ALLOWED_PREFIXES):
            raise HTTPException(400, "Please upload a JPG, PNG or WEBP photo.")
        try:
            obs, model = vision.analyse(body.image, body.note)
        except vision.VisionError as e:
            return {"ok": False, "message": str(e)}

        decision = vision.route(obs)
        agent = get_agent(body.session_id)
        observed = vision.describe(obs)
        if decision["topic"] is None:
            return {"ok": True, "routed": False, "observed": observed, "message": decision["message"],
                    "caveat": CAVEAT, "model": model, "view": agent.view()}

        # Start the guide now; the browser shows it only after the user confirms what the AI saw.
        agent.start(decision["topic"], via="photo")
        for reason in decision["reasons"]:
            agent.escalate(reason)
        # Questions the photo clearly answers are answered for the user (and shown to them), not asked again.
        agent.photo_auto = vision.auto_answers(decision["topic"], obs)
        auto_notes = [note for _, note in agent.photo_auto.values()]
        t = TOPICS[decision["topic"]]
        return {"ok": True, "routed": True, "observed": observed, "reasons": decision["reasons"],
                "auto_notes": auto_notes,
                "topic": {"id": decision["topic"], "title": t["title"], "icon": t["icon"]},
                "caveat": CAVEAT, "model": model, "view": agent.view()}

    @app.get("/api/photo/health")
    def photo_health(request: Request, test: int = 0):
        """Open /api/photo/health?test=1 to check that the vision model answers (shows the exact error if not)."""
        out = {"key_found": bool(os.getenv("GROQ_API_KEY")), "models": vision.vision_models()}
        if test:
            rate_limit(request, limit=4, window=60)
            out["test"] = vision.selftest()
        return out
