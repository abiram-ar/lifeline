"""
LifeLine photo add-on: small upgrades to the existing Agent, added WITHOUT editing agent.py.

  1. The photo can pre-answer triage questions it can see (see vision.auto_answer), so the agent
     doesn't ask "does the skin look white or charred?" when the photo already shows it.
  2. Emergency interrupt: typing "he stopped breathing" or "she collapsed" in the Ask box at any
     moment (even mid-questions) re-plans straight away (CPR, or the unconscious guide).
  3. TYPED UPDATES in every guide: whatever the person types in the Ask box is read as (a) the answer to the
     question on screen, (b) "done / next", (c) news about the situation ("the seizure stopped", "I switched
     off the power", "his face is drooping"), or (d) a normal question. The AI never writes steps: it can
     only pick among actions that already exist in knowledge.py (answer a question, move a step, add a red flag,
     switch protocol). Anything unclear falls back to the normal grounded Q&A.

This works by wrapping a few Agent methods at start-up. No web libraries are needed here, so it is easy to test.
"""
import re

import llm
from agent import WHAT_TO_DO, Agent, normalize
from knowledge import TOPICS

# ------------------------------------------------------------------ typed updates (all guides)
_QUESTION_START = re.compile(r"^\s*(?:can|could|should|shall|is|are|do|does|will|would|may|how|what|when|why|where|which|who)\b")
_YES = re.compile(r"^\s*(?:yes|yeah|yep|yup|yea|y|haan|haa|ha|sure|correct|true)\b[\s,.!]*", re.I)
_NO = re.compile(r"^\s*(?:no|nope|nah|n|nahi|nahin|not really|negative)\b[\s,.!]*", re.I)
_DONE = re.compile(r"^\s*(?:done|done it|did it|i did(?: it)?|finished|completed|ok(?:ay)? done|next|next step|ok next|got it)\W*$", re.I)
_WORSE = re.compile(r"\b(?:getting worse|gets worse|got worse|worsening|worse now|much worse|worse)\b")
_BETTER_CHECKIN_NO = re.compile(r"\b(?:not better|no better|not improving|no improvement|same|worse|still)\b")


def _is_question(text):
    return "?" in text or bool(_QUESTION_START.match(text.lower().strip()))


def _yes_no(text):
    """Short literal answers only: 'yes', 'no', 'no he is fine'. Returns True/False/None."""
    if _YES.match(text):
        return True
    m = _NO.match(text)
    if m and len(text[m.end():].split()) <= 6 and " but " not in text.lower():
        return False
    return None


# What typed words mean for each triage question (same order as TOPICS[topic]["triage"]).
# A match means the answer to that question is YES (the dangerous direction), so a wrong match only
# causes extra caution. None = nothing to match (those questions are covered by the collapse rule).
_H = re.compile
TRIAGE_HINTS = {
    "bleeding": [_H(r"spurt\w*|pool\w*|soak\w*|gush\w*|pour\w*|a lot of blood|lots of blood|heavy|won'?t stop|not stopping|blood everywhere"),
                 _H(r"\b(?:pale|cold|clammy|sweat\w*|dizzy|confus\w*|faint\w*|drowsy)\b")],
    "burn": [_H(r"\b(?:face|facial|hands?|fingers?|feet|foot|toes?|genital\w*|joints?|knees?|elbows?|eyes?)\b|(?:bigger|larger) than (?:a |his |her |my |the )?palm|large burn|big burn"),
             _H(r"electric\w*|chemical|acid|smoke|inhal\w*|fumes|hot air"),
             _H(r"\b(?:white|leathery|charred|black|waxy)\b")],
    "stroke": [_H(r"droop\w*|uneven|crooked|lopsided|face (?:is )?(?:numb|weak)"),
               _H(r"\barms?\b.*(?:weak|drift\w*|can'?t|numb|heavy)|can'?t (?:raise|lift)|one arm"),
               _H(r"slurr\w*|can'?t (?:speak|talk)|unable to (?:speak|talk)|garbl\w*|confus\w*|gibberish")],
    "seizure": [_H(r"first (?:time|seizure|fit)|never had|(?:more than|over|longer than) (?:5|five)\b|still (?:shaking|seizing|jerking)|another|second|again|repeated"),
                _H(r"\b(?:water|pool|river|bath\w*|injur\w*|hurt|bleeding|pregnant)\b|trouble breathing|struggling to breathe")],
    "asthma": [_H(r"can'?t (?:speak|talk|finish)|\b(?:blue|grey|gray)\b|too breathless|gasping"),
               _H(r"no inhaler|don'?t have (?:an? )?inhaler|without (?:an? )?inhaler|inhaler (?:is )?(?:empty|missing|lost)|forgot (?:the |his |her )?inhaler")],
    "snakebite": [_H(r"droop\w*|double vision|blurr\w*|can'?t (?:speak|swallow|talk)|\bgums?\b|trouble (?:speaking|swallowing|breathing)|difficulty (?:speaking|swallowing|breathing)"),
                  None],
    "animal_bite": [_H(r"heav\w* bleed\w*|bleeding (?:a lot|heavily|badly)|\b(?:face|head|neck)\b"),
                    _H(r"stray|unknown|wild|strange\w*|rabid|foaming|street|not (?:our|my) (?:dog|pet)")],
    "fracture": [_H(r"bone (?:is )?(?:stick\w*|visible|show\w*|out)|bent|deform\w*|twisted|odd shape|bleeding (?:a lot|heavily|badly)"),
                 _H(r"\b(?:head|neck|back|spine)\b|fell from|fall from|crash|accident"),
                 _H(r"\b(?:cold|pale|blue|numb|tingl\w*)\b")],
    "chemical": [_H(r"\beyes?\b"),
                 _H(r"swallow\w*|drank|\bate\b|ingest\w*|fumes?|coughing|struggl\w* to breathe")],
    "heatstroke": [_H(r"not sweating|stopped sweating|hot and dry|dry skin|confus\w*|dizzy|uncoordinated|disorient\w*|slurr\w*")],
    "electric": [_H(r"still (?:touching|holding|connected|live|sparking)|power ?line|live wire|downed|fallen wire"), None],
    # literal answer: "is the person breathing normally?" -> yes
    "unresponsive": [_H(r"(?<!not )(?<!n't )\bbreath(?:ing|es|e) (?:normally|normal|fine|ok|okay|well)")],
}

# News that moves the guide. (regex, what to do, step title it refers to)
#   jump = go to that step   finish = go to the check-in question
STEP_REPORTS = {
    "bleeding": [(_H(r"soak\w* through|(?:bleeding|coming|seeping) through"), "jump", "If blood soaks through")],
    "burn": [(_H(r"still (?:burning|on fire)|clothes? (?:are |is )?on fire|flames"), "jump", "Stop the burning")],
    "choking": [(_H(r"coughed (?:it )?(?:up|out)|coughing (?:it )?(?:up|out)|spat (?:it )?out|threw (?:it )?up|came out|object (?:is )?out|can breathe now|breathing again"), "finish", None)],
    "seizure": [(_H(r"(?:stopped|stops) (?:shaking|jerking|convuls\w*)|(?:jerking|shaking|seizure|fit) (?:has |have |is )?(?:stopped|over|ended)"), "jump", "When the jerking stops")],
    "asthma": [(_H(r"not (?:helping|working)|no better|still (?:breathless|wheezing|struggling)"), "jump", "Still not better?")],
    "anaphylaxis": [(_H(r"no (?:change|improvement)|not (?:better|improving|working)|still (?:swollen|wheezing|struggling|bad)"), "jump", "Second dose")],
    "electric": [(_H(r"(?:switched|turned|cut|shut)\s+(?:it\s+|the\s+|off\s+)*(?:off|power|mains|electricity)|power (?:is |has been )?(?:off|cut)|unplugged"), "jump", "Check once it is safe"),
                 (_H(r"still (?:touching|holding|connected|live|sparking)"), "jump", "Don't touch them yet")],
}


def _llm_yes_no(question, text):
    """Ask the language model ONLY how a message answers one yes/no question. Returns True/False/None."""
    if not llm.enabled():
        return None
    reply = llm.chat_json([
        {"role": "system", "content":
            "A bystander is answering a first-aid question in their own words. Decide whether their message "
            "clearly answers this ONE yes/no question. Reply with JSON only: "
            '{"answer": "yes" | "no" | "unsure"}. Use "unsure" unless the message clearly answers it. '
            "Never explain. Never give medical advice."},
        {"role": "user", "content": f"QUESTION: {question}\nMESSAGE: {text[:300]}"},
    ], max_tokens=20)
    ans = str(reply.get("answer", "")).lower() if reply else ""
    return True if ans == "yes" else False if ans == "no" else None


def _jump_to(agent, title):
    for i, s in enumerate(agent.steps()):
        if s["title"] == title:
            agent.step_i = i
            return True
    return False


def _typed_update(agent, text):
    """Read free text as an update to the guide that is open. Returns an answer dict, or None to fall back to Q&A."""
    topic = agent.topic
    info = TOPICS[topic]
    t = normalize(text).lower()
    action = agent.choose_action()
    kind = action["kind"]
    hints = TRIAGE_HINTS.get(topic, [])

    # (a) answer to the question on screen
    if kind == "triage":
        q = info["triage"][action["index"]]
        hint = hints[action["index"]] if action["index"] < len(hints) else None
        answer = _yes_no(text)
        if answer is None and hint and hint.search(t):
            answer = True
        if answer is None:
            answer = _llm_yes_no(q["q"], text)
        if answer is None:
            return None
        agent.answer_triage(answer)
        msg = "Got it, I've noted that."
        if agent.escalated:
            msg += " Call 112 / 108 now."
        return {"answer": msg + " Carry on with the next question on screen.", "via": "rules"}

    if kind == "checkin":
        answer = _yes_no(text)
        if answer is None and _BETTER_CHECKIN_NO.search(t):
            answer = False
        if answer is None:
            return None
        agent.answer_checkin(answer)
        return {"answer": "Got it, I've noted that.", "via": "rules"}

    if kind != "step":
        return None

    # (b) "done" / "next"
    if _DONE.match(text):
        agent.next_step()
        return {"answer": "OK, here is the next step.", "via": "rules"}

    # (c) news about the situation
    done = []
    for rx, what, title in STEP_REPORTS.get(topic, []):
        if rx.search(t):
            if what == "jump" and title and _jump_to(agent, title):
                done.append(f"Moving to '{title}'.")
            elif what == "finish":
                agent.step_i = len(agent.steps())
                done.append("Good. Let me check how things are now.")
            break
    # new danger signs: the same hints used for the questions now add a red flag
    for i, q in enumerate(info["triage"]):
        hint = hints[i] if i < len(hints) else None
        if hint and q.get("trigger", "yes") == "yes" and not q.get("switch") and hint.search(t):
            if q["flag"] not in agent.reasons:
                agent.escalate(q["flag"])
                done.append("That is a warning sign. Call 112 / 108 now.")
    if _WORSE.search(t) and "Condition is getting worse" not in agent.reasons:
        agent.escalate("Condition is getting worse")
        done.append("If it is getting worse, call 112 / 108 now.")
    if done:
        return {"answer": " ".join(done), "via": "rules"}
    return None


# ------------------------------------------------------------------ emergency interrupt
# "not breathing" type phrases -> CPR. Typos are corrected first ("breathng").
_NOT_BREATHING = re.compile(
    r"(?:not|isn'?t|aren'?t|no longer|stopped|stops|stop|without)\s+(?:a\s+)?breath(?:ing|e)?"
    r"|no breathing|doesn'?t breathe|can'?t find (?:a )?pulse|no pulse|heart stopped|cardiac arrest|stopped moving")
# collapse type phrases -> unconscious guide (which checks breathing first). A leading "not" cancels them.
_COLLAPSED = re.compile(
    r"(?<!not )(?<!n't )(?<!never )\b(?:collapsed|passed out|fainted|unconscious|unresponsive|knocked out|blacked out|"
    r"went limp|gone limp|won'?t wake|not waking|not responding|doesn'?t respond)\b")


# While the CPR guide is open, the person may answer the "Check breathing" step by typing.
_NOT_NORMAL = re.compile(r"\b(?:gasping|gasps|snoring|barely breath\w*|struggling to breath\w*|noisy breath\w*)\b")
_BREATHING_OK = re.compile(
    r"(?<!not )(?<!n't )(?<!never )\bbreath(?:ing|es|e)\s+(?:normally|normal|fine|ok|okay|well|properly|again)\b"
    r"|\bstarted breathing\b|\bis breathing\b|\bare breathing\b")


def _cpr_alt_index(agent):
    """Index of the CPR step that has the 'They ARE breathing normally' button (Check breathing)."""
    for i, s in enumerate(agent.steps()):
        if s.get("alt"):
            return i
    return None


def _cpr_reply(agent, question):
    """The person is on the CPR guide and tells us something about breathing.
    Treat it as the answer to the 'Check breathing' step instead of ignoring it.
    Returns an answer dict, or None if the text is not about breathing."""
    t = normalize(question).lower()
    alt_i = _cpr_alt_index(agent)
    if alt_i is None:
        return None

    if _NOT_BREATHING.search(t) or _NOT_NORMAL.search(t):
        if agent.step_i <= alt_i:
            agent.step_i = alt_i + 1               # breathing check answered: go to the compressions
            agent.notice = "Not breathing normally: start chest compressions now."
            return {"answer": "Not breathing normally means start chest compressions now. "
                              "Push hard and fast in the centre of the chest. Make sure 112 / 108 has been called.",
                    "via": "rules"}
        return {"answer": "Keep going with the steps on screen. Push hard and fast, and don't stop "
                          "until help takes over or they start breathing normally.", "via": "rules"}

    if _BREATHING_OK.search(t):
        agent.step_i = alt_i                       # same as pressing the "They ARE breathing normally" button
        agent.take_alt()
        return {"answer": "Good. Switching to the recovery position guide. Keep watching their breathing "
                          "and keep 112 / 108 on the way.", "via": "rules"}
    return None


def detect_interrupt(text, current_topic):
    """Return the protocol to switch to, or None."""
    t = normalize(text).lower()
    if _NOT_BREATHING.search(t):
        return "cpr" if current_topic != "cpr" else None
    if _COLLAPSED.search(t):
        return "unresponsive" if current_topic not in ("cpr", "unresponsive") else None
    return None


_orig_ask = Agent.ask


def _ask(self, question):
    if self.topic:
        t = normalize(question).lower()
        # 1. a new emergency (not breathing -> CPR, collapsed -> unconscious guide, which checks breathing first)
        target = detect_interrupt(question, self.topic)
        if target and target in TOPICS:
            title = TOPICS[target]["title"]
            self._switch(target, "New emergency reported: " + question.strip()[:60])
            self.notice = f"Switched to '{title}' because of what you just reported."
            if target == "cpr":
                _skip_to_compressions(self)
            return {"answer": f"Switching to '{title}' now. Follow the steps on screen and call 112 / 108.", "via": "rules"}
        # 2. the CPR guide: typing about breathing answers the "Check breathing" step
        if self.topic == "cpr":
            reply = _cpr_reply(self, question)
            if reply:
                return reply
        # 3. every other guide: typed answers, "done", and news about the situation
        if not _is_question(question):
            reply = _typed_update(self, question)
            if reply:
                return reply
        else:
            # A panicked message often mixes news and a question: "he's still touching the wire, what to do?"
            # Act on the news first (so the screen is up to date), then answer the question about THIS moment.
            clauses = [c.strip() for c in re.split(r"[?.;!,]", question) if c.strip()]
            news = [c for c in clauses if not _is_question(c) and not WHAT_TO_DO.search(normalize(c).lower())]
            update = _typed_update(self, ", ".join(news)) if news else None
            answer = _orig_ask(self, question)
            if update:
                answer = {**answer, "answer": update["answer"] + " " + answer["answer"]}
            return answer
    return _orig_ask(self, question)


# ------------------------------------------------------------------ "not breathing" reported mid-guide
def _skip_to_compressions(agent):
    """The person has ALREADY said 'not breathing', so don't make them check again:
    start the CPR guide at the chest-compressions step. (Back still returns to 'Check and call'.)"""
    for i, st in enumerate(agent.steps()):
        if st.get("tool") == "metronome":
            agent.step_i = i
            agent.notice = ("You said they are not breathing, so start chest compressions now. "
                            "Call 112 / 108 now (red buttons) and ask someone to bring an AED.")
            return


_orig_start = Agent.start


def _start(self, topic, infant=False, via="button"):
    previous = self.topic
    _orig_start(self, topic, infant, via)
    # The server's emergency-pattern shortcut ("he is not breathing" typed while another guide is open)
    if topic == "cpr" and via == "emergency-pattern" and previous not in (None, "cpr"):
        _skip_to_compressions(self)


# ------------------------------------------------------------------ photo answers
_orig_reset, _orig_choose, _orig_view = Agent.reset, Agent.choose_action, Agent.view


def _reset(self):
    _orig_reset(self)
    self.photo_auto = {}      # {question text: (answer, note)} waiting to be applied
    self.photo_notes = []     # notes about answers already applied, shown to the user


def _choose_action(self):
    """Apply any photo answers that match the question we are about to ask, then carry on as normal."""
    while True:
        action = _orig_choose(self)
        pending = getattr(self, "photo_auto", None)
        if action.get("kind") == "triage" and pending and action["text"] in pending:
            answer, note = pending.pop(action["text"])
            self.photo_notes.append(note)
            self.answer_triage(answer)
            continue
        return action


def _view(self):
    self.choose_action()                      # apply photo answers first so the view isn't stale
    v = _orig_view(self)
    v["photo_notes"] = list(getattr(self, "photo_notes", []))
    return v


def install():
    if getattr(Agent, "_photo_patched", False):
        return
    Agent.ask, Agent.reset, Agent.choose_action, Agent.view = _ask, _reset, _choose_action, _view
    Agent.start = _start
    Agent._photo_patched = True


install()