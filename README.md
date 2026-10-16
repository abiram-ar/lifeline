# LifeLine: AI First Aid Assistant

A goal-based AI agent that guides a bystander through first aid, one step at a time, with a mobile-friendly website.
Built for **Fundamentals of AI (23RAI111)**. Python backend (FastAPI) + plain HTML/CSS/JS front end.
Free tools only: the **Groq API** (free key) for language understanding.

## Run it (2 minutes)

```bash
cd lifeline
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                     # then paste your free key into .env
python server.py                                         # open http://localhost:8000
```

Get the free key at https://console.groq.com/keys (no card needed). **No key? It still works** in offline mode
with built-in rules. Run the tests any time: `python -m unittest discover -s tests -v`.

To try it on your phone: run with `HOST=0.0.0.0 python server.py` and open `http://<your-laptop-ip>:8000` on the same Wi-Fi.

## What it does

- **Describe it your way**: type, speak (🎤), or tap a card. Understands messy text. Hindi/Malayalam input should work through Groq (best effort, not yet tested).
- **Guided flow**: quick red-flag questions → one step at a time → "did it work?" check-in.
- **Re-plans**: choking → person collapses → switches to CPR; "he stopped breathing" typed anywhere switches to CPR.
- **Smart tools**: countdown timers (cool a burn 20 min, press a wound 10 min), a 110 BPM CPR beat with sound + pulse.
- **Hands-free**: 🔊 reads each step aloud.
- **Emergency clock**: shows when it started and how long ago (useful for stroke, snakebite, heart attack).
- **"What to tell the operator"**: auto-built script (location, emergency, danger signs, what you've done) with
  📍 share location, 🏥 nearest hospital (opens Google Maps) and 📋 copy. Location works on localhost or https only.
- **Search** the emergency cards, and **install it as an app** on a phone (PWA: "Add to Home Screen").
- **Ask a question** ("can I give water?"): answered by Groq using **only** the on-screen protocol, or from the guide offline.
- **16 protocols**: CPR, unconscious, heavy bleeding, burns, choking (adult + baby), heart attack, stroke, seizure,
  severe allergy, asthma, snakebite, dog/animal bite, fracture, chemical splash, heatstroke, electric shock.
- India-first: 112 / 108 / 101 / 100, Indian snakebite and rabies protocols.

## How it is built (use this in your report)

```
Browser (static/)  ──JSON──▶  server.py (FastAPI)  ──▶  agent.py  ──▶  knowledge.py   (fixed, sourced protocols)
                                                          │
                                                          └──▶  llm.py ──▶ Groq        (optional)
```

| Course concept | In the code |
|---|---|
| **Agent type: goal-based** | `Agent.choose_action()` picks the next action from the internal model to reach the goal "stable, or help on the way" |
| **Percepts / sensors** | text, voice (browser speech-to-text), button taps, yes/no answers |
| **Internal model** | `Agent.reset()` attributes: topic, triage position, step, `escalated`, `reasons`, `infant` |
| **Actuators** | on-screen steps, spoken steps, emergency call buttons, timers, CPR beat |
| **Goal / re-planning** | `Agent._switch()` abandons a protocol when the situation worsens |
| **Performance measure** | correctness vs. official guidance (`tests/`), time-to-first-instruction, correct escalation |
| **Environment** | stressed bystander, partially observable (agent only knows what the user reports), dynamic |

### Safety design (the important part)

1. **The AI never writes medical steps.** Every instruction is fixed text in `knowledge.py`, tied to named sources.
2. Groq is used only to (a) route messy text to a protocol, (b) answer follow-ups from the protocol text. Temperature 0.
3. A **dose guard** rejects any AI answer that mentions a drug quantity not already in the protocol.
4. Emergency phrases ("not breathing") are caught by a **local pattern before any network call**.
5. If the AI is down or rate-limited, rules take over automatically. Rate limit + short cooldown protect the free quota.
6. Every protocol shows its **sources**, and topics resting on weaker sources are flagged "Awaiting expert review".
7. Over-triage by design: when unsure, the agent escalates (more severe topic wins ties; any red flag → call 112/108).

## What the research changed from the first draft

| Topic | Change | Source |
|---|---|---|
| Burns | Cool **20 minutes**, not 10 | British Red Cross, Australian Red Cross |
| Bleeding | Soaked dressing: **replace**, don't pile on; don't wash a heavily bleeding wound | British Red Cross |
| Snakebite | **No tourniquet, no tight bandage**; R.I.G.H.T. (Reassure, Immobilise, Go to hospital, Tell the doctor) | Indian national protocol |
| Chemical | Eye rinse ≥10 min, don't force out contact lenses; skin ≥20 min; brush off powder first | St John Ambulance |
| Heart attack | Aspirin only **if the operator advises** and no allergy | St John Ambulance |
| Dog bite | 15 min soap-and-water wash, rabies vaccination even for small bites; no haldi/oil/chilli | National rabies guidance |
| Fractures | Dropped R.I.C.E. (for mild sprains only) | Current guidance |

Where sources disagree, the choice is written in each topic's `notes` field.

## ⚠ Before you demo or submit: verification checklist

- [ ] Open every source link in `knowledge.py` and compare the wording once. **Two topics are marked `verify`** (fracture, electric shock): they rest on a county emergency-services page, not a Red Cross page. Re-check them against the Red Cross / St John pages.
- [ ] Ideally ask a doctor, nurse or certified first-aider to review the protocols. Say in your report that this is a student prototype and has not been clinically validated.
- [ ] Test with a Groq key **and** without one.

## Known limits (be honest about these in your report)

- Understands only what the user reports. It cannot see or examine the person.
- Offline keyword fallback doesn't understand negation ("he is *not* bleeding").
- Guidance text is in English; only the *understanding* of input is multilingual.
- Voice input uses the browser's speech service (Chrome sends audio to Google). Text sent to Groq for understanding leaves your server. Don't type personal details.
- Sessions live in memory (cleared when the server restarts). Not hardened for public hosting.

## Ideas for the next phase

Malayalam/Hindi translations of the fixed protocols (reviewed by a human), photo input for wounds, GPS to show the nearest
hospital with antivenom, an offline PWA, and a utility-based upgrade (rank actions by expected benefit).

## Files

```
server.py         web API + serves the site
agent.py          the goal-based agent, understanding, grounded Q&A
knowledge.py      sourced protocols (the only place medical text lives)
llm.py            Groq client (standard library only)
static/           index.html, style.css, app.js, sw.js, manifest, icons
tests/            22 offline tests
```