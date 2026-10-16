"""
LifeLine photo add-on: look at a photo and decide which guide to open.

SAFETY DESIGN (the important part):
  1. The vision model is ONLY an observer. It fills in a fixed form of "what is visible"
     (person lying down? vehicle? heavy bleeding? ...). It is told not to diagnose.
  2. Every answer is validated against a list of allowed values. Anything else becomes "unclear".
  3. FIXED RULES in route() turn those observations into a protocol. The AI never picks
     the medical advice, and never writes it.
  4. A photo can't show a spine injury or internal bleeding. So any crash or fall scene opens
     the "assume the worst" protocol, whatever the person looks like.
  5. The photo is sent to Groq for analysis and is NOT saved by LifeLine.

Uses the standard library only. Needs GROQ_API_KEY (same free key as the rest of the app).
"""
import json
import os
import re
import struct
import urllib.error
import urllib.request
import zlib

API_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/") + "/chat/completions"
# Groq retired its Llama 4 vision model in July 2026; Qwen is the documented replacement.
# If this changes again, set GROQ_VISION_MODEL="model1,model2" in .env.
DEFAULT_VISION_MODELS = ["qwen/qwen3.8-27b", "qwen/qwen3.6-27b"]

last_error = ""


class VisionError(Exception):
    """A problem we can explain to the user in one sentence."""


# --------------------------------------------------------------------------- the fixed "form"
ALLOWED = {
    "person_position": {"lying_on_ground", "sitting", "standing", "unclear", "none"},
    "scene": {"road_crash", "fall", "fire_or_burn", "animal_or_snake", "chemical", "medical", "other", "unclear"},
    "helmet_on": {"yes", "no", "unclear", "not_applicable"},
    "visible_bleeding": {"none", "minor", "heavy", "unclear"},
    "appears_unresponsive": {"yes", "no", "unclear"},
    "burn_location": {"face_hands_feet_genitals_or_joint", "other_body_area", "unclear"},
    "burn_size": {"bigger_than_palm", "smaller_than_palm", "unclear"},
    "burn_appearance": {"red_only", "blistered", "white_leathery_or_charred", "unclear"},
}
BOOLS = ["person_visible", "vehicle_involved", "visible_bone_or_deformity", "visible_burn", "snake_visible"]
DANGERS = {"traffic", "fire", "smoke", "fuel_or_chemical", "electrical", "water"}

SYSTEM_PROMPT = """You are a visual observer inside a first-aid app. Look at the photo and fill in a JSON form.
Rules:
- Report ONLY what is clearly visible. Do NOT diagnose and do NOT guess injuries you cannot see.
- If you are not sure about a field, use "unclear" (or false for yes/no fields).
- Never identify or name anyone.
- Reply with ONE JSON object and nothing else.

Fields (use exactly these names and allowed values):
"person_visible": true or false
"person_position": "lying_on_ground" | "sitting" | "standing" | "unclear" | "none"
"scene": "road_crash" (vehicle collision, bike or motorcycle crash) | "fall" (fall from a height, or someone fallen)
         | "fire_or_burn" | "animal_or_snake" | "chemical" | "medical" (no visible injury) | "other" | "unclear"
"vehicle_involved": true or false (bike, motorcycle, scooter, car, truck)
"helmet_on": "yes" | "no" | "unclear" | "not_applicable"
"visible_bleeding": "none" | "minor" | "heavy" | "unclear"
"visible_bone_or_deformity": true or false (bone showing or a limb clearly bent the wrong way)
"visible_burn": true or false
"snake_visible": true or false
"appears_unresponsive": "yes" | "no" | "unclear"
"burn_location": "face_hands_feet_genitals_or_joint" | "other_body_area" | "unclear"   (only if a burn is visible)
"burn_size": "bigger_than_palm" | "smaller_than_palm" | "unclear"   (compared with the person's own palm; use "unclear" unless you can tell)
"burn_appearance": "red_only" | "blistered" | "white_leathery_or_charred" | "unclear"   (only if a burn is visible)
"danger_in_scene": list from ["traffic","fire","smoke","fuel_or_chemical","electrical","water"], empty list if none
"""


# --------------------------------------------------------------------------- talking to Groq
def vision_models():
    raw = os.getenv("GROQ_VISION_MODEL", "")
    chosen = [m.strip() for m in raw.split(",") if m.strip()]
    return chosen or DEFAULT_VISION_MODELS


def extract_json(text):
    """Pull the first JSON object out of a model reply (ignores <think> blocks and code fences)."""
    if not text:
        return None
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _post(body, key, timeout=35):
    req = urllib.request.Request(
        API_URL, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": "lifeline-first-aid/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)
    return (data["choices"][0]["message"].get("content") or "").strip()


def analyse(data_url, note=""):
    """Send the photo to Groq. Returns (observations, model_used). Raises VisionError."""
    global last_error
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise VisionError("Photo analysis needs the AI connection (no GROQ_API_KEY found).")

    user_text = "Fill in the form for this photo."
    if note.strip():
        user_text += f" The user added this note (unverified): {note.strip()[:300]}"
    base = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [{"type": "text", "text": user_text},
                                         {"type": "image_url", "image_url": {"url": data_url}}]},
        ],
        "temperature": 0,
        "max_completion_tokens": 1000,
    }
    # Different models accept different extras. Try the richest request first, then simpler ones.
    variants = [
        {"response_format": {"type": "json_object"}, "reasoning_effort": "low"},
        {"response_format": {"type": "json_object"}},
        {},
    ]
    problem = ""
    for model in vision_models():
        for extra in variants:
            body = {**base, **extra, "model": model}
            try:
                reply = _post(body, key)
            except urllib.error.HTTPError as e:
                try:
                    detail = e.read().decode("utf-8", "replace")[:200]
                except Exception:
                    detail = ""
                problem = f"HTTP {e.code} for {model}: {detail}"
                print(f"[photo] {problem}")
                if e.code in (401, 403):
                    last_error = problem
                    raise VisionError("Groq rejected the key. Check GROQ_API_KEY in your .env file.")
                if e.code == 429:
                    last_error = problem
                    raise VisionError("The AI is busy (rate limit). Wait a minute and try again.")
                if e.code == 400:
                    continue            # this variant isn't accepted: try a simpler one
                break                   # 404 or 5xx: try the next model
            except Exception as e:      # timeout, no internet, ...
                problem = f"{type(e).__name__}: {e}"
                print(f"[photo] {problem}")
                break
            raw = extract_json(reply)
            if raw is not None:
                last_error = ""
                return normalise(raw), model
            problem = f"{model} did not return JSON"
    last_error = problem
    raise VisionError("I couldn't analyse that photo. Please describe what happened instead, or tap a card.")


# --------------------------------------------------------------------------- validation
def normalise(raw):
    """Force the model's answer into the allowed form. Unknown values become 'unclear'."""
    obs = {}
    for field, allowed in ALLOWED.items():
        v = str(raw.get(field, "unclear")).strip().lower()
        obs[field] = v if v in allowed else "unclear"
    for field in BOOLS:
        obs[field] = raw.get(field) is True
    d = raw.get("danger_in_scene", [])
    obs["danger_in_scene"] = sorted({str(x).lower() for x in d} & DANGERS) if isinstance(d, list) else []
    return obs


# --------------------------------------------------------------------------- fixed rules: observations -> protocol
def route(obs):
    """Decide which guide to open. Returns {"topic", "reasons", "message"}.
    Rules are checked from most to least dangerous. Photos can't rule things out, so we over-triage."""
    reasons = []
    if obs["visible_bleeding"] == "heavy":
        reasons.append("Heavy bleeding visible in the photo")
    if obs["appears_unresponsive"] == "yes":
        reasons.append("The person looks unresponsive")
    for d in obs["danger_in_scene"]:
        reasons.append({"traffic": "Traffic danger at the scene", "fire": "Fire at the scene",
                        "smoke": "Smoke at the scene", "fuel_or_chemical": "Fuel or chemical danger at the scene",
                        "electrical": "Electrical danger at the scene", "water": "Water danger at the scene"}[d])

    lying = obs["person_position"] == "lying_on_ground"
    topic = None
    if obs["snake_visible"] or obs["scene"] == "animal_or_snake":
        if obs["person_visible"]:
            topic = "snakebite"
        else:
            return {"topic": None, "reasons": [], "message":
                    "I can see a snake but no injured person. Keep well away from it. If anyone has been bitten, tap Snakebite below."}
    elif obs["scene"] == "road_crash" or (obs["vehicle_involved"] and lying) or (obs["scene"] == "fall" and lying):
        topic = "major_trauma"
        if not obs["person_visible"]:
            reasons.append("Crash scene, but no person is clearly visible in the photo: check for anyone hurt nearby")
    elif obs["scene"] == "fire_or_burn" or obs["visible_burn"]:
        topic = "burn"
    elif obs["scene"] == "chemical":
        topic = "chemical"
    elif obs["visible_bleeding"] == "heavy":
        topic = "bleeding"
    elif obs["visible_bone_or_deformity"]:
        topic = "fracture"

    if topic is None:
        return {"topic": None, "reasons": [], "message":
                "I can't tell from this photo what happened. Please describe it in words, or tap the closest card."}
    return {"topic": topic, "reasons": reasons, "message": ""}


def describe(obs):
    """Plain-English list of what the model reported seeing (shown to the user to confirm)."""
    out = []
    if obs["person_visible"]:
        pos = {"lying_on_ground": "lying on the ground", "sitting": "sitting", "standing": "standing"}.get(obs["person_position"])
        out.append("A person" + (f", {pos}" if pos else ""))
    else:
        out.append("No person clearly visible")
    scene = {"road_crash": "Looks like a road crash", "fall": "Looks like a fall",
             "fire_or_burn": "Fire or a burn", "animal_or_snake": "An animal or snake",
             "chemical": "A chemical or spill"}.get(obs["scene"])
    if scene:
        out.append(scene)
    if obs["vehicle_involved"]:
        out.append("A bike, motorcycle or other vehicle is involved")
    if obs["helmet_on"] == "yes":
        out.append("A helmet is on (leave it on)")
    if obs["visible_bleeding"] in ("minor", "heavy"):
        out.append(f"{obs['visible_bleeding'].capitalize()} bleeding visible")
    if obs["visible_bone_or_deformity"]:
        out.append("A limb looks deformed or a bone is showing")
    if obs["visible_burn"]:
        out.append("A burn is visible")
        loc = {"face_hands_feet_genitals_or_joint": "on the face, a hand, a foot, the genitals or a joint",
               "other_body_area": "on another body area"}.get(obs.get("burn_location"))
        if loc:
            out.append(f"The burn is {loc}")
        look = {"red_only": "The skin looks red", "blistered": "The skin looks blistered",
                "white_leathery_or_charred": "The skin looks white, leathery or charred"}.get(obs.get("burn_appearance"))
        if look:
            out.append(look)
    if obs["snake_visible"]:
        out.append("A snake is visible")
    if obs["appears_unresponsive"] == "yes":
        out.append("The person looks unresponsive")
    elif obs["appears_unresponsive"] == "unclear" and obs["person_visible"]:
        out.append("I can't tell if they are responsive")
    return out


# --------------------------------------------------------------------------- let the photo answer questions it can SEE
# Rules: the photo may answer a triage question only when the answer is clearly visible.
# Questions about things a photo can't show (breathing, electricity, chemicals...) are always asked.
# Every auto-answer is shown to the user, who can switch to the full question list.
def auto_answer(topic, question, obs):
    """Return (answer, note) for a triage question the photo answers, else (None, None)."""
    q = question.lower()
    if topic == "burn":
        if "over a joint" in q:
            if obs.get("burn_location") == "face_hands_feet_genitals_or_joint" or obs.get("burn_size") == "bigger_than_palm":
                return True, "Photo: the burn is on a high-risk area or looks larger than a palm. Answered Yes."
        if "white, leathery or charred" in q:
            look = obs.get("burn_appearance")
            if look == "white_leathery_or_charred":
                return True, "Photo: the skin looks white, leathery or charred. Answered Yes."
            if look in ("red_only", "blistered"):
                return False, "Photo: the skin looks red or blistered, not white, leathery or charred. Answered No."
    if topic == "bleeding" and "spurting" in q and obs.get("visible_bleeding") == "heavy":
        return True, "Photo: heavy bleeding is visible. Answered Yes."
    if topic == "fracture" and ("bone visible" in q or "bone is visible" in q or "bent out of shape" in q) \
            and obs.get("visible_bone_or_deformity") is True:
        return True, "Photo: a bone or a bent limb is visible. Answered Yes."
    return None, None


def auto_answers(topic, obs):
    """{question text: (answer, note)} for every triage question of this topic the photo can answer."""
    from knowledge import TOPICS
    found = {}
    for q in TOPICS[topic]["triage"]:
        ans, note = auto_answer(topic, q["q"], obs)
        if ans is not None:
            found[q["q"]] = (ans, note)
    return found


# --------------------------------------------------------------------------- self-test (used by /api/photo/health?test=1)
def _tiny_png(size=64, rgb=(180, 180, 180)):
    row = b"\x00" + bytes(rgb) * size
    raw = zlib.compress(row * size)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", raw) + chunk(b"IEND", b""))
    import base64
    return "data:image/png;base64," + base64.b64encode(png).decode()


def selftest():
    try:
        obs, model = analyse(_tiny_png())
        return {"ok": True, "model": model, "sample": obs}
    except VisionError as e:
        return {"ok": False, "error": str(e), "detail": last_error, "models": vision_models()}
