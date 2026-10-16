"""
LifeLine photo add-on: the "Road crash / serious fall" protocol.

It is added to the existing knowledge base at import time, so knowledge.py does not
need to be edited. As everywhere in LifeLine, the steps are FIXED text. The photo
analysis never writes advice; it only helps choose this protocol.

REVIEW STATUS: "verify". The wording matches several secondary sources (Mayo Clinic,
which cites the American Red Cross manual; a BHS/SkillBase fact sheet; Hong Kong Red Cross
and St John Ambulance advice quoted by SCMP; British Red Cross rider advice via Devitt).
I did not read a British Red Cross or St John Ambulance spinal-injury page directly.
Compare this text with those pages before relying on it, and ideally have a first-aider
review it.
"""
from knowledge import TOPICS

TRAUMA_TOPIC = {
    "icon": "🏍️", "title": "Road crash / serious fall", "category": "critical",
    "severity": "critical", "review": "verify",
    "summary": "Bike or vehicle crash, or a fall from a height. Assume a spine or head injury: keep them still and call for help.",
    "keywords": ["crash", "collision", "road accident", "bike accident", "motorbike", "motorcycle", "scooter",
                 "hit by a", "knocked down", "fell from", "fall from", "spinal", "spine", "neck injury",
                 "back injury", "head injury", "accident$"],
    "always_escalate": "Serious crash or fall: assume a spine or head injury until a doctor says otherwise",
    "triage": [
        {"q": "Look at their chest without moving them. Is the person breathing normally? (Gasping, or no chest movement, is NOT normal.)",
         "flag": "Crash victim is not breathing normally", "trigger": "no", "switch": "cpr"},
    ],
    "steps": [
        {"title": "Make the scene safe", "text": "Don't put yourself in danger. If you can do it safely, ask others to slow or stop traffic, switch off any engine, and keep onlookers and flames away from spilled fuel."},
        {"title": "Call 112 / 108 now", "text": "Call, or send someone to call. Say it is a road crash with a possible spine or head injury, and give the exact location. Stay on the line, and ask someone to bring a first-aid kit."},
        {"title": "Do not move them", "text": "Keep them exactly as you found them, even if they say they feel fine. Tell them to stay still, especially their head and neck. Moving the neck or back can cause permanent paralysis."},
        {"title": "Leave the helmet on", "text": "Do not take off a helmet. It supports the head and neck. If it seems to be blocking their breathing and you can't check it, tell the emergency operator and follow their instructions."},
        {"title": "Support the head", "text": "Without moving them, you can hold the head and neck still with your hands, or put rolled towels or soft clothing on both sides of the head, until help arrives."},
        {"title": "Heavy bleeding?", "text": "If blood is spurting or soaking through clothes, press firmly on the wound with a clean cloth, without moving their body, and keep pressing."},
        {"title": "Reassure and keep warm", "text": "Keep talking to them calmly. Cover them with a coat or blanket. Don't give food or drink."},
        {"title": "Watch the breathing", "text": "Keep watching their chest. If they stop breathing normally, they need CPR straight away: breathing comes before protecting the spine. If they are breathing normally, keep still and wait for the ambulance.",
         "alt": {"label": "They are NOT breathing normally", "switch": "cpr",
                 "notice": "Switched to CPR because the person is not breathing normally."}},
    ],
    "avoid": [
        "Don't move, lift or sit them up, even to make them comfortable.",
        "Don't take off their helmet.",
        "Don't let them stand or walk, even if they say they're fine.",
        "Don't give food, drink or medicines.",
        "Don't pull them out of a vehicle unless there is fire or another immediate danger to life.",
    ],
    "call_when": ["Always. Call 112 / 108 for any serious crash or fall, even if the person seems fine."],
    "after_care": "Stay with them and keep them still until the ambulance team takes over. Tell the crew what happened, how you found them, and what you did.",
    "notes": "Assume a spine injury after any serious crash or fall: a photo, or how the person feels, cannot rule it out. The 'leave the helmet on' advice is consistent across the sources. The head-support step comes from Mayo Clinic only. 'CPR before spine protection' follows standard resuscitation priorities. VERIFY against British Red Cross / St John Ambulance pages.",
    "sources": [
        {"name": "Mayo Clinic: spinal injury first aid (cites American Red Cross)", "url": "https://mayoclinic.org/first-aid/first-aid-basics/basics/ART-20056677"},
        {"name": "BHS / SkillBase fact sheet: suspected spinal injuries", "url": "https://www.bhs.org.uk/media/zg0je4kg/bhs-head-injury-updated-26-02-1.pdf"},
        {"name": "SCMP: Hong Kong Red Cross and St John on spinal injuries", "url": "https://amp.scmp.com/lifestyle/health-wellness/article/3188232/spinal-injuries-how-be-smart-first-responder-accident"},
        {"name": "Rider first aid with British Red Cross (Devitt)", "url": "https://www.devittinsurance.com/?p=122777"},
    ],
}


def register():
    """Add the topic to the shared knowledge base (safe to call many times)."""
    TOPICS.setdefault("major_trauma", TRAUMA_TOPIC)


register()
