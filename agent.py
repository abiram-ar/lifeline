"""
LifeLine - the agent (no web code in here, so it is easy to test and to explain).

GOAL-BASED AGENT, step by step (Russell & Norvig):
  PERCEIVE      understand() / start()      read what the user said, pick a protocol
  MODEL         the attributes of Agent     topic, triage position, step, escalated...
  GOAL          "person is safe and stable, or professional help is on the way"
  CHOOSE ACTION choose_action()             look at the model, decide what to show next
  RE-PLAN       answer_triage(switch=...)   things got worse -> change the whole plan

Where the language model (Groq) is used, and where it is NOT:
  USED      1. understanding messy free text ("my dad's gone grey and is clutching his chest")
            2. answering follow-up questions, using the protocol text as the ONLY source
  NEVER     writing or changing the medical steps. Those are fixed in knowledge.py.
  Emergency words ("not breathing") are caught by a local pattern first, so the
  alarm never waits for a network call.
"""
import difflib
import re
import uuid

import llm
from knowledge import TOPICS, URGENT_PATTERNS

SEVERITY_RANK = {"critical": 0, "urgent": 1, "moderate": 2}
STOPWORDS = set("a an the is are was were be to of and or it in on at for with my his her their can i you do does should "
                "what how when why if not no yes they them he she this that there then so but as from by".split())


# --------------------------------------------------------------------------- helpers
# Words people commonly misspell when panicking. Close misspellings are corrected
# before matching, so "chocking" or "bleding" still reach the right protocol.
KNOWN_WORDS = ["choking", "choked", "bleeding", "burning", "burned", "scalded", "seizure", "convulsing",
               "snakebite", "unconscious", "unresponsive", "breathing", "breathless", "allergic", "asthma",
               "fractured", "dislocated", "heatstroke", "collapsed", "electrocuted", "drowning", "fainted"]


def normalize(text):
    out = []
    for token in re.findall(r"\S+", text):
        core = re.sub(r"[^a-zA-Z']", "", token).lower()
        if len(core) >= 6 and core not in KNOWN_WORDS:
            close = difflib.get_close_matches(core, KNOWN_WORDS, n=1, cutoff=0.88)
            if close:
                out.append(close[0])
                continue
        out.append(token)
    return " ".join(out)


def _words(text):
    return re.findall(r"[a-z']+", text.lower())


def keyword_scores(text):
    """Score every topic by how many of its keywords appear in the text.
    Phrases count double. A trailing '$' means 'exact word' (so 'cut$' won't match 'cute')."""
    t = text.lower()
    words = _words(t)
    scores = {}
    for tid, info in TOPICS.items():
        score = 0
        for kw in info["keywords"]:
            if kw.endswith("$"):
                base = kw[:-1]
                if any(w == base or w == base + "s" for w in words):
                    score += 1
            elif " " in kw:
                if kw in t:
                    score += 2
            elif any(w.startswith(kw) for w in words):
                score += 1
        scores[tid] = score
    return scores


def keyword_topic(text):
    """Best topic from rules alone, or None if nothing/tie. Ties prefer the more severe topic."""
    scores = keyword_scores(text)
    best = max(scores.values())
    if best == 0:
        return None
    winners = [t for t, s in scores.items() if s == best]
    if len(winners) == 1:
        return winners[0]
    winners.sort(key=lambda t: SEVERITY_RANK[TOPICS[t]["severity"]])
    top = [t for t in winners if SEVERITY_RANK[TOPICS[t]["severity"]] == SEVERITY_RANK[TOPICS[winners[0]]["severity"]]]
    return top[0] if len(top) == 1 else None


def urgent_topic(text):
    """Local emergency check. Runs before (and instead of) the language model."""
    t = text.lower()
    for pattern, topic in URGENT_PATTERNS:
        if re.search(pattern, t):
            return topic
    return None


def protocol_text(topic_id):
    """The protocol flattened to plain text: this is the only knowledge the Q&A model gets."""
    t = TOPICS[topic_id]
    steps = t.get("steps", [])
    lines = [f"EMERGENCY: {t['title']}. {t['summary']}"]
    lines += [f"STEP {i + 1} ({s['title']}): {s['text']}" for i, s in enumerate(steps)]
    lines += [f"DO NOT: {a}" for a in t.get("avoid", [])]
    lines += [f"CALL 112/108 WHEN: {c}" for c in t.get("call_when", [])]
    if t.get("after_care"):
        lines.append(f"AFTERWARDS: {t['after_care']}")
    return "\n".join(lines)


# "what to do?", "what should I do now", "help": the person wants the next action, not a topic
WHAT_TO_DO = re.compile(r"\bwhat (?:to do|should i do|do i do|can i do|shall i do|now|next)\b|\bwhat to do\b|\bhelp me\b|\bwhat now\b")


# --------------------------------------------------------------------------- understanding
def understand(text):
    """Work out which protocol the user means.
    Returns {"topic": id|None, "infant": bool, "via": str}."""
    clean = normalize(text)
    infant = any(w in clean.lower() for w in ("baby", "infant", "newborn", "months old", "month old"))

    urgent = urgent_topic(clean)
    if urgent:
        return {"topic": urgent, "infant": infant, "via": "emergency-pattern"}

    if llm.enabled():
        catalogue = "\n".join(f"- {tid}: {t['title']}. {t['summary']}" for tid, t in TOPICS.items())
        reply = llm.chat_json([
            {"role": "system", "content":
                "You route first-aid emergencies. Pick the ONE protocol that best matches the user's message. "
                "The message may be in any language and may be messy or panicked.\n"
                f"PROTOCOLS:\n{catalogue}\n\n"
                'Reply with JSON only: {"topic": "<id or none>", "infant": <true if the patient is a baby under 1 year>, '
                '"confidence": <0 to 1>}. Use "none" if no protocol fits or the message is not an emergency. '
                "Never explain. Never give medical advice."},
            {"role": "user", "content": text[:600]},
        ], max_tokens=60)
        if reply:
            tid = reply.get("topic")
            try:
                conf = float(reply.get("confidence", 0))
            except (TypeError, ValueError):
                conf = 0.0
            if tid in TOPICS and conf >= 0.5:
                return {"topic": tid, "infant": bool(reply.get("infant")) or infant, "via": "groq"}

    return {"topic": keyword_topic(clean), "infant": infant, "via": "keywords"}


# --------------------------------------------------------------------------- the agent
class Agent:
    def __init__(self):
        self.session_id = uuid.uuid4().hex[:12]
        self.reset()

    # ---- MODEL: what the agent currently believes about the situation
    def reset(self):
        self.topic = None
        self.infant = False
        self.tri_i = 0
        self.step_i = 0
        self.checkin_done = False
        self.resolved = False       # GOAL reached?
        self.escalated = False      # professional help needed?
        self.reasons = []
        self.notice = ""            # one-off message, e.g. "switched to CPR because ..."
        self.needs_clarification = False
        self.via = ""

    def escalate(self, reason):
        self.escalated = True
        if reason not in self.reasons:
            self.reasons.append(reason)

    def start(self, topic, infant=False, via="button"):
        """Begin (or restart) a protocol."""
        self.reset()
        self.topic = topic
        self.infant = bool(infant) and "steps_infant" in TOPICS[topic]
        self.via = via
        reason = TOPICS[topic].get("always_escalate")
        if reason:
            self.escalate(reason)
        if self.infant:
            self.escalate("Emergency involving a baby: get help now")

    # ---- PERCEIVE
    def perceive(self, text):
        """Read free text. Returns True if a protocol was chosen."""
        result = understand(text)
        if result["topic"] is None:
            self.reset()
            self.needs_clarification = True
            self.via = result["via"]
            return False
        self.start(result["topic"], result["infant"], result["via"])
        return True

    def _switch(self, topic, reason):
        """RE-PLAN: the situation changed, so abandon this protocol and start another."""
        old = TOPICS[self.topic]["title"]
        carried = list(self.reasons)
        self.start(topic, via="re-plan")
        for r in carried + [reason]:
            self.escalate(r)
        self.notice = f"Switched from '{old}' to '{TOPICS[topic]['title']}': {reason.lower()}."

    # ---- UPDATE MODEL from the user's answers
    def answer_triage(self, yes):
        q = TOPICS[self.topic]["triage"][self.tri_i]
        alarm = yes if q.get("trigger", "yes") == "yes" else (not yes)
        self.notice = ""
        if alarm:
            if q.get("switch"):
                self._switch(q["switch"], q["flag"])
                return
            self.escalate(q["flag"])
        self.tri_i += 1

    def next_step(self):
        self.notice = ""
        self.step_i += 1

    def prev_step(self):
        self.notice = ""
        if self.step_i > 0:
            self.step_i -= 1
        elif self.tri_i > 0:
            self.tri_i -= 1

    def take_alt(self):
        """The user pressed the alternative button on a step (e.g. 'They ARE breathing normally')."""
        steps = self.steps()
        if self.topic is None or self.step_i >= len(steps) or not steps[self.step_i].get("alt"):
            return
        alt = steps[self.step_i]["alt"]
        self.start(alt["switch"], via="re-plan")
        self.tri_i = len(TOPICS[alt["switch"]]["triage"])      # the user already answered that question
        self.notice = alt.get("notice", "")

    def answer_checkin(self, better):
        self.notice = ""
        self.checkin_done = True
        if better:
            self.resolved = True
        else:
            self.escalate(TOPICS[self.topic]["escalate_if_no"])

    # ---- CHOOSE ACTION
    def steps(self):
        info = TOPICS[self.topic]
        return info["steps_infant"] if self.infant and "steps_infant" in info else info["steps"]

    def choose_action(self):
        if self.topic is None:
            return {"kind": "clarify" if self.needs_clarification else "idle"}
        info = TOPICS[self.topic]
        if self.tri_i < len(info["triage"]):
            return {"kind": "triage", "text": info["triage"][self.tri_i]["q"],
                    "index": self.tri_i, "total": len(info["triage"])}
        steps = self.steps()
        if self.step_i < len(steps):
            s = steps[self.step_i]
            return {"kind": "step", "index": self.step_i, "total": len(steps),
                    "title": s["title"], "text": s["text"],
                    "timer": s.get("timer"), "tool": s.get("tool"), "alt": s.get("alt")}
        if not self.escalated and not self.checkin_done and info.get("checkin"):
            return {"kind": "checkin", "text": info["checkin"]}
        return {"kind": "done"}

    def view(self):
        """Everything the screen needs, as plain JSON."""
        t = TOPICS.get(self.topic) if self.topic else None
        return {
            "session_id": self.session_id,
            "topic": ({"id": self.topic, "title": t["title"], "icon": t["icon"], "severity": t["severity"],
                       "summary": t["summary"]} if t else None),
            "action": self.choose_action(),
            "escalated": self.escalated,
            "reasons": self.reasons,
            "resolved": self.resolved,
            "notice": self.notice,
            "step_titles": [s["title"] for s in self.steps()] if t else [],
            "avoid": t["avoid"] if t else [],
            "call_when": t.get("call_when", []) if t else [],
            "after_care": t.get("after_care", "") if t else "",
            "notes": t.get("notes", "") if t else "",
            "review": t.get("review", "") if t else "",
            "sources": t["sources"] if t else [],
            "ai": {"enabled": llm.enabled(), "via": self.via},
        }

    # ---- grounded Q&A
    def screen_context(self):
        """What the person is looking at right now, in words. Given to the Q&A model so it answers about THIS moment."""
        act = self.choose_action()
        lines = []
        if act["kind"] == "step":
            lines.append(f"Current step {act['index'] + 1} of {act['total']} ({act['title']}): {act['text']}")
        elif act["kind"] in ("triage", "checkin"):
            lines.append(f"Question on screen: {act['text']}")
        if self.reasons:
            lines.append("Red flags so far: " + "; ".join(self.reasons))
        return "\n".join(lines)

    def what_to_do_now(self):
        """Offline answer to 'what to do?': the step on screen, or the first step if questions are still pending."""
        act = self.choose_action()
        steps = self.steps()
        if act["kind"] == "step":
            return f"Right now: {act['title']}. {act['text']}"
        if steps:
            return (f"Start with this: {steps[0]['title']}. {steps[0]['text']} "
                    "Then answer the question on screen.")
        return None

    def ask(self, question):
        """Answer a follow-up question using ONLY this protocol. Returns {"answer", "via"}."""
        if self.topic is None:
            return {"answer": "Tell me what happened first, then I can help.", "via": "rules"}
        if urgent_topic(normalize(question)) == self.topic:
            return {"answer": "You're already on the right guide. Keep following the steps on screen, "
                              "and make sure 112 / 108 has been called.", "via": "rules"}
        proto = protocol_text(self.topic)
        screen = self.screen_context()

        if llm.enabled():
            reply = llm.chat([
                {"role": "system", "content":
                    "You are a calm first-aid assistant helping a bystander during an emergency in India. "
                    "Answer the question using ONLY the PROTOCOL below. Rules:\n"
                    "- If the protocol does not answer it, say you can't advise on that and tell them to ask the "
                    "emergency operator on 112 or 108.\n"
                    "- Never contradict the protocol. Never invent steps, medicines or doses.\n"
                    "- At most 3 short sentences in plain, simple words. No lists, no markdown.\n"
                    "- If the situation sounds like it is getting worse, tell them to call 112/108 now.\n"
                    "- The person may describe what is happening AND ask a question in one message. Use both. "
                    "If they describe an ongoing danger, say the protocol's safe action for it first.\n"
                    "- If they ask what to do, tell them what the CURRENT STEP says and what the PROTOCOL says "
                    "to avoid, in your own simple words.\n\n"
                    f"PROTOCOL:\n{proto}\n\nWHAT THE PERSON SEES NOW:\n{screen or 'nothing yet'}"},
                {"role": "user", "content": question[:400]},
            ], max_tokens=160)
            if reply and self._answer_is_safe(reply, proto):
                return {"answer": reply, "via": "groq"}

        if WHAT_TO_DO.search(normalize(question).lower()):
            now = self.what_to_do_now()
            if now:
                return {"answer": now, "via": "rules"}
        return {"answer": self._offline_answer(question, proto), "via": "rules"}

    @staticmethod
    def _answer_is_safe(answer, proto):
        """Reject answers that mention a dose or quantity that is not in the protocol."""
        for m in re.finditer(r"\d+(?:\.\d+)?\s?(?:mg|ml|mcg|tablets?|pills?|drops?)", answer.lower()):
            if m.group(0).replace(" ", "") not in proto.lower().replace(" ", ""):
                return False
        return True

    @staticmethod
    def _offline_answer(question, proto):
        """No AI available: return the protocol sentence that best matches the question."""
        q = {w for w in _words(question) if w not in STOPWORDS and len(w) > 2}
        best, best_score = None, 0
        for line in proto.splitlines():
            overlap = len(q & {w for w in _words(line) if w not in STOPWORDS})
            if overlap > best_score:
                best, best_score = line, overlap
        if best and best_score >= 2:
            prefix = re.match(r"^(STEP \d+ \([^)]*\): |DO NOT: |CALL 112/108 WHEN: |AFTERWARDS: |EMERGENCY: )", best)
            label = prefix.group(1) if prefix else ""
            body = best[len(label):]
            if label.startswith("DO NOT"):
                body = "Don't: " + body
            elif label.startswith("CALL"):
                body = "Call 112 / 108 when: " + body
            return body
        return ("I can't answer that from the guide. Keep following the steps, and if you're unsure, "
                "call 112 or 108 and ask the operator.")
