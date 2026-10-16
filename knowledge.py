"""
LifeLine - first-aid knowledge base.

EVERY instruction here is fixed text, written from the published guidance listed
in each topic's `sources`. A language model is NEVER allowed to invent or change
medical steps; it may only (a) work out which protocol the user means and
(b) answer follow-up questions using the protocol text as its only source.

Guidance used (checked October 2026):
  - British Red Cross first aid pages (bleeding, burns, choking, unresponsive)
  - St John Ambulance first aid advice (heart attack, seizure, anaphylaxis,
    stroke, chemical burns)
  - NHS (asthma attack, heat exhaustion/heatstroke, stroke symptoms)
  - Resuscitation Council UK (CPR)
  - British Red Cross: broken bone page (fractures)
  - St John Ambulance UK and St John Ambulance NSW (electric shock)
  - Indian national snakebite protocol (WHO Snakebite Treatment Group /
    Tamil Nadu Snakebite Taskforce, published in Indian Pediatrics) and
    India's national rabies prophylaxis guidance
Emergency numbers are Indian: 112 (all emergencies), 108 (ambulance).

REVIEW STATUS: `review` = "sourced" means the steps were cross-checked against at
least one of the named official pages. Topics marked "verify" rest on a weaker
source and MUST be checked by the team (ideally with a doctor) before demo day.

Where the organisations disagree, the choice made is noted in `notes`.

Step format:  {"title", "text", optional "timer" (seconds), optional "tool"}
Triage question: {"q", "flag", optional "trigger": "yes"|"no", optional "switch"}
  trigger "yes" (default): answering YES raises the alarm / switches protocol
  trigger "no": answering NO raises the alarm / switches protocol
"""

EMERGENCY_NUMBERS = [
    {"number": "112", "label": "All emergencies"},
    {"number": "108", "label": "Ambulance"},
    {"number": "101", "label": "Fire"},
    {"number": "100", "label": "Police"},
]

CATEGORIES = [
    ("critical", "Life-threatening"),
    ("injury", "Injuries"),
    ("medical", "Sudden illness"),
    ("india", "Bites, heat and chemicals"),
]

TOPICS = {
    # ------------------------------------------------------------------ CPR
    "cpr": {
        "icon": "🫀", "title": "Not breathing / cardiac arrest", "category": "critical",
        "severity": "critical", "review": "sourced",
        "summary": "Person is not responding and not breathing normally. Start CPR now.",
        "keywords": ["cpr", "cardiac", "resuscitat"],
        "always_escalate": "Not breathing normally is life-threatening",
        "triage": [],
        "steps": [
            {"title": "Check and call", "text": "Gently shake their shoulders and shout. No response? Shout for help and call 112 / 108 on loudspeaker. Ask someone to fetch an AED (defibrillator) if there is one nearby."},
            {"title": "Check breathing", "text": "Look at the chest and listen for up to 10 seconds. Gasping, snoring or noisy breathing is NOT normal breathing. If they ARE breathing normally, tap the button below this step. If not, go to the next step.",
             "alt": {"label": "They ARE breathing normally", "switch": "unresponsive",
                     "notice": "Switched to the recovery-position guide because the person is breathing normally."}},
            {"title": "Push hard and fast", "text": "Kneel beside them. Put the heel of one hand on the centre of the chest, other hand on top, fingers interlocked. Push down firmly about 5-6 cm, twice per second (100-120 per minute). Don't stop.", "tool": "metronome"},
            {"title": "Rescue breaths (only if trained)", "text": "If you are trained and willing: after every 30 pushes, tilt the head back, pinch the nose and give 2 breaths that make the chest rise. Otherwise keep pushing without stopping."},
            {"title": "Use the AED", "text": "When an AED arrives, switch it on and follow its voice instructions. Keep pushing while the pads are put on, except when it tells you not to touch the person.", "tool": "metronome"},
            {"title": "Keep going", "text": "Continue until the AED tells you to pause, an ambulance team takes over, or the person starts to breathe normally and wake up. Swap with another helper every 2 minutes if you can.", "tool": "metronome"},
        ],
        "avoid": [
            "Don't stop pushing to check for a pulse.",
            "Don't worry about cracking a rib. That is far better than no CPR.",
            "Don't give food or drink.",
        ],
        "call_when": ["Always. Call 112 / 108 first, before starting."],
        "after_care": "Keep going until the ambulance team takes over. Tell them when the person collapsed and what you did.",
        "notes": "Children and babies need different depth and hand position. The emergency operator will guide you on the phone.",
        "sources": [
            {"name": "Resuscitation Council UK: CPR", "url": "https://www.resus.org.uk/cpr"},
            {"name": "British Red Cross: unresponsive and not breathing", "url": "https://www.redcross.org.uk/first-aid/learn-first-aid"},
        ],
    },
    # ---------------------------------------------------------- UNRESPONSIVE
    "unresponsive": {
        "icon": "😵", "title": "Unconscious / fainted", "category": "critical",
        "severity": "critical", "review": "sourced",
        "summary": "Person has collapsed and is not responding. First step is to check breathing.",
        "keywords": ["unconscious", "unresponsive", "faint", "collaps", "passed out", "blacked out", "not responding"],
        "always_escalate": "An unresponsive person needs urgent medical help",
        "triage": [
            {"q": "Look at the chest and listen for up to 10 seconds. Is the person breathing normally? (Gasping, snoring or noisy breaths do NOT count as normal.)",
             "flag": "Unresponsive and not breathing normally", "trigger": "no", "switch": "cpr"},
        ],
        "steps": [
            {"title": "Open the airway", "text": "Tilt the head back gently and lift the chin to keep the airway open."},
            {"title": "Recovery position", "text": "Roll them onto their side: bend the top knee so the body can't roll forward, rest the top hand under the cheek, and keep the head tilted back so the mouth drains."},
            {"title": "Call for help", "text": "Call 112 / 108 now if you have not already. Stay with them."},
            {"title": "Keep checking", "text": "Watch their breathing all the time. If it stops or becomes abnormal, roll them onto their back and start CPR."},
        ],
        "avoid": [
            "Don't give food, drink or medicines.",
            "Don't leave them alone.",
            "Don't sit them up or prop them against a wall.",
        ],
        "call_when": ["Always for someone who does not wake up."],
        "after_care": "Stay with them until help arrives. Tell the responders how long they were unconscious and anything you saw before they collapsed.",
        "notes": "Someone who faints and wakes up within a minute still needs a doctor's check if it is their first time, or if they hit their head.",
        "sources": [
            {"name": "St John Ambulance: unresponsive and breathing", "url": "https://www.sja.org.uk/first-aid-advice/"},
            {"name": "British Red Cross: unresponsive and breathing", "url": "https://www.redcross.org.uk/first-aid/learn-first-aid"},
        ],
    },
    # -------------------------------------------------------------- BLEEDING
    "bleeding": {
        "icon": "🩸", "title": "Heavy bleeding", "category": "critical",
        "severity": "urgent", "review": "sourced",
        "summary": "Blood that is spurting, soaking through cloth, or won't stop.",
        "keywords": ["bleed", "blood", "gash", "stab", "lacerat", "wound", "cut$"],
        "triage": [
            {"q": "Is the blood spurting, pooling on the floor, or soaking through cloth quickly?",
             "flag": "Severe bleeding"},
            {"q": "Is the person pale, cold, sweaty, dizzy or confused?",
             "flag": "Signs of shock from blood loss"},
        ],
        "steps": [
            {"title": "Press on the wound", "text": "Press firmly and directly on the wound with a clean cloth or whatever you have. You are acting as a plug, and the pressure helps the blood clot. If you can, put on gloves or a plastic bag first. The person can press with their own hand."},
            {"title": "Something stuck in the wound?", "text": "Do NOT pull it out. It is helping plug the hole. Press firmly on both sides of it instead."},
            {"title": "Keep pressing", "text": "Don't lift the cloth to check. Keep steady pressure for at least 10 minutes, or until help arrives.", "timer": 600},
            {"title": "If blood soaks through", "text": "Remove the soaked cloth and replace it with a fresh one. Make sure the pressure is firm, directly over the wound."},
            {"title": "Bandage firmly", "text": "When the bleeding slows, tie a firm bandage over the pad. It should be snug, not so tight that fingers or toes turn cold, pale or blue."},
            {"title": "Treat for shock", "text": "If they look pale, cold or dizzy: keep pressing, lay them down, lift their legs higher than their heart (unless a leg is injured), and cover them with a coat or blanket."},
        ],
        "avoid": [
            "Don't pull out objects stuck in the wound.",
            "Don't wash a wound that is bleeding heavily. It may bleed more.",
            "Don't use home remedies like powders or turmeric.",
            "Don't give food or drink.",
        ],
        "checkin": "Has the bleeding stopped or clearly slowed after 10 minutes of firm pressure?",
        "escalate_if_no": "Bleeding that will not stop needs emergency care",
        "call_when": [
            "Blood is spurting or soaking through cloth quickly",
            "Bleeding hasn't slowed after 10 minutes of pressure",
            "The wound is in the chest or belly, or an object is stuck in it",
            "The person looks pale, cold, dizzy or confused",
        ],
        "after_care": "Keep the wound clean and covered. See a doctor if it is deep, gaping, dirty, or from an animal or rusty object (a tetanus shot may be needed).",
        "notes": "British Red Cross and St John say to REPLACE a soaked dressing; some ambulance trusts say to add on top. We follow the Red Cross. Tourniquets are deliberately not taught here: the emergency operator can guide that.",
        "sources": [
            {"name": "British Red Cross: bleeding heavily", "url": "https://www.redcross.org.uk/first-aid/learn-first-aid/bleeding-heavily"},
            {"name": "St John Ambulance: severe bleeding", "url": "https://www.sja.org.uk/first-aid-advice/severe-bleeding"},
        ],
    },
    # ----------------------------------------------------------------- BURNS
    "burn": {
        "icon": "🔥", "title": "Burn or scald", "category": "injury",
        "severity": "urgent", "review": "sourced",
        "summary": "From fire, hot water, steam or hot oil. Cool it for at least 20 minutes.",
        "keywords": ["burn", "scald", "boiling", "steam", "hot oil"],
        "triage": [
            {"q": "Is the burn on the face, hands, feet, genitals or over a joint, or bigger than the person's palm?",
             "flag": "Large or high-risk burn"},
            {"q": "Was it caused by electricity or a chemical, or did the person breathe in smoke or hot air?",
             "flag": "Electrical/chemical burn or smoke inhalation"},
            {"q": "Does the skin look white, leathery or charred?", "flag": "Possible deep burn"},
        ],
        "steps": [
            {"title": "Stop the burning", "text": "Move away from the heat source. If clothes are on fire: stop, drop and roll, or smother the flames with a blanket."},
            {"title": "Cool the burn", "text": "Hold it under cool (not ice-cold) running water for at least 20 minutes. The sooner and longer it is cooled, the less the damage. Keep cooling even if it still hurts.", "timer": 1200},
            {"title": "Remove tight items", "text": "While cooling, gently take off rings, watches and loose clothing near the burn before it swells. Leave anything that is stuck to the skin."},
            {"title": "Cover it", "text": "After cooling, cover loosely with cling film or a clean plastic bag, laid on lengthways, not wrapped round. It keeps the burn clean and reduces pain."},
        ],
        "avoid": [
            "Don't use ice, iced water, butter, oil or toothpaste.",
            "Don't burst blisters.",
            "Don't peel off clothing that is stuck to the burn.",
            "Don't use fluffy cotton wool or sticky dressings.",
        ],
        "checkin": "Is the burn small (smaller than the person's palm) and is the pain settling after 20 minutes of cooling?",
        "escalate_if_no": "Burns that are not settling need urgent medical care",
        "call_when": [
            "The burn is larger than the person's palm, or deep (white, charred or leathery)",
            "It is on the face, hands, feet, genitals or a joint",
            "It was caused by chemicals or electricity, or smoke was inhaled",
            "The person is a baby, a child or elderly: always get medical advice",
        ],
        "after_care": "Burns are often painful even after cooling. Keep it clean and covered. See a doctor if blisters form or it looks infected (more pain, pus, fever). Any burn on a baby or child needs medical advice.",
        "sources": [
            {"name": "British Red Cross: burns and scalds", "url": "https://www.redcross.org.uk/first-aid/learn-first-aid/burns"},
            {"name": "Australian Red Cross: burns", "url": "https://redcross.org.au/firstaid/basics/burn"},
        ],
    },
    # --------------------------------------------------------------- CHOKING
    "choking": {
        "icon": "😮", "title": "Choking", "category": "critical",
        "severity": "urgent", "review": "sourced",
        "summary": "Something is stuck in the throat and they can't cough, speak or breathe.",
        "keywords": ["chok", "gag", "windpipe", "stuck in throat", "swallowed wrong"],
        "triage": [
            {"q": "Has the person collapsed or stopped responding?",
             "flag": "Choking person is unresponsive", "switch": "cpr"},
        ],
        "steps": [
            {"title": "Check: are they choking?", "text": "Ask 'Are you choking?' If they can cough, speak or breathe, encourage them to keep coughing and stay with them. Only continue if they cannot cough, speak or breathe (they may clutch their throat or go silent)."},
            {"title": "5 back blows", "text": "Bend them forwards. Give up to 5 firm blows between the shoulder blades with the heel of your hand. After each blow, check whether the object has come out."},
            {"title": "5 abdominal thrusts", "text": "Still choking? Stand behind them, make a fist and place it just above the belly button, below the ribs. Grip it with your other hand and pull sharply inwards and upwards, up to 5 times."},
            {"title": "Call and repeat", "text": "Still not clear? Send someone to call 112 / 108 now. Keep alternating 5 back blows and 5 thrusts until it comes out or help arrives. If they stop responding, start CPR."},
        ],
        "steps_infant": [
            {"title": "Position the baby", "text": "Sit or kneel. Lay the baby face-down along your forearm and thigh, supporting the head and jaw, with the head lower than the bottom."},
            {"title": "5 back blows", "text": "Give up to 5 firm blows between the shoulder blades with the heel of your hand. Check the mouth after each blow."},
            {"title": "5 chest thrusts", "text": "Turn the baby face-up along your thigh, head lower than the body. Push down on the centre of the chest with two fingers, up to 5 times, sharply and slowly."},
            {"title": "Call and repeat", "text": "Call 112 / 108 now. Keep alternating 5 back blows and 5 chest thrusts. If the baby goes limp or stops responding, start baby CPR as the operator directs."},
        ],
        "avoid": [
            "Don't slap the back if they can still cough or speak.",
            "Don't poke blindly into the mouth. Only remove an object you can see.",
            "NEVER give abdominal thrusts to a baby under one year.",
        ],
        "checkin": "Did the object come out, and is the person breathing normally?",
        "escalate_if_no": "Blockage not cleared",
        "call_when": [
            "Back blows haven't cleared it",
            "The person becomes unresponsive",
            "You gave abdominal or chest thrusts: always see a doctor afterwards",
        ],
        "after_care": "Anyone who needed back blows or thrusts should be checked by a doctor, even if they feel fine.",
        "notes": "Children over one year are helped like adults, with less force on the back blows.",
        "sources": [
            {"name": "British Red Cross: choking", "url": "https://www.redcross.org.uk/first-aid/learn-first-aid/choking"},
            {"name": "St John Ambulance: adult choking", "url": "https://www.sja.org.uk/first-aid-advice/choking"},
        ],
    },
    # ------------------------------------------------------------ HEART ATTACK
    "heart_attack": {
        "icon": "💔", "title": "Chest pain / heart attack", "category": "critical",
        "severity": "critical", "review": "sourced",
        "summary": "Crushing chest pain, pain spreading to the arm or jaw, sweating, breathlessness.",
        "keywords": ["heart attack", "chest pain", "chest tight", "crushing", "angina", "pain in chest", "left arm"],
        "always_escalate": "Suspected heart attack: every minute matters",
        "triage": [
            {"q": "Has the person collapsed or stopped responding?",
             "flag": "Collapsed with suspected heart attack", "switch": "cpr"},
        ],
        "steps": [
            {"title": "Call now", "text": "Call 112 / 108 and say you think someone is having a heart attack. Do not drive them yourself."},
            {"title": "Sit them down", "text": "Help them into the most comfortable position: ideally on the floor, knees bent, head and shoulders supported. Reassure them."},
            {"title": "Aspirin (only if advised)", "text": "Only if the emergency operator advises it, the person is an adult, and they are NOT allergic to aspirin: give one adult aspirin tablet (about 300 mg) to chew slowly. Never give it to anyone under 16."},
            {"title": "Their own medicine", "text": "If they have angina medication (for example a GTN spray or tablet), help them use it."},
            {"title": "Watch closely", "text": "Stay with them and watch their breathing and responses. If they become unresponsive and stop breathing normally, start CPR."},
        ],
        "avoid": [
            "Don't let them walk about or 'sleep it off'.",
            "Don't give aspirin to anyone under 16 or anyone allergic to it.",
            "Don't give food or drink.",
        ],
        "call_when": ["Always. Suspected heart attack is an emergency."],
        "after_care": "Stay with them until the ambulance arrives. Tell the crew when the pain started.",
        "notes": "St John Ambulance's current poster says to give aspirin only if advised on the emergency call; we follow that.",
        "sources": [
            {"name": "St John Ambulance: heart attack", "url": "https://www.sja.org.uk/first-aid-advice/heart-attack/"},
        ],
    },
    # ----------------------------------------------------------------- STROKE
    "stroke": {
        "icon": "🧠", "title": "Stroke", "category": "critical",
        "severity": "critical", "review": "sourced",
        "summary": "Face drooping, arm weakness, slurred speech. Act FAST.",
        "keywords": ["stroke", "face droop", "slurred", "drooping", "cant lift arm", "can't lift arm", "speech problem"],
        "always_escalate": "Suspected stroke: time is critical",
        "triage": [
            {"q": "FACE: ask them to smile. Is the smile uneven, or is the mouth or eye drooping?", "flag": "Face weakness"},
            {"q": "ARMS: ask them to raise both arms. Can they only raise one, or does one drift down?", "flag": "Arm weakness"},
            {"q": "SPEECH: ask 'What is your name?' Is the speech slurred, confused, or are they unable to answer?", "flag": "Speech problems"},
        ],
        "steps": [
            {"title": "Call now", "text": "Call 112 / 108 and say you suspect a stroke, using the FAST signs you saw. Note the time the signs started."},
            {"title": "Keep them comfortable", "text": "Help them sit or lie in a comfortable, supported position. Reassure them."},
            {"title": "Nothing by mouth", "text": "Don't give food, drink or medicines. Swallowing may be difficult."},
            {"title": "Stay and watch", "text": "Stay with them and watch their responses and breathing. If they become unresponsive, check breathing and follow the unresponsive guide."},
        ],
        "avoid": [
            "Don't wait to see if the signs pass. Symptoms that settle still need urgent help.",
            "Don't drive them yourself. The operator will advise.",
            "Don't give food, drink or aspirin.",
        ],
        "call_when": ["Any one FAST sign, even if it seems to be getting better."],
        "after_care": "Tell the ambulance crew exactly when the symptoms began.",
        "sources": [
            {"name": "St John Ambulance: stroke", "url": "https://www.sja.org.uk/get-advice/first-aid-advice/stroke"},
            {"name": "NHS: symptoms of a stroke", "url": "https://www.nhs.uk/content-widgets/health-a-to-z/stroke/symptoms"},
        ],
    },
    # ---------------------------------------------------------------- SEIZURE
    "seizure": {
        "icon": "⚡", "title": "Seizure / fit", "category": "medical",
        "severity": "urgent", "review": "sourced",
        "summary": "Jerking movements, stiffening, or sudden loss of awareness.",
        "keywords": ["seizure", "fit$", "epilep", "convuls", "shaking uncontrollably", "jerking"],
        "triage": [
            {"q": "Is this their first seizure, or has it lasted more than 5 minutes, or is another one following?",
             "flag": "First, prolonged or repeated seizure"},
            {"q": "Is the person in water, injured, pregnant, or having trouble breathing afterwards?",
             "flag": "Seizure with added danger"},
        ],
        "steps": [
            {"title": "Note the time", "text": "Look at the clock and note when it started. Ask onlookers to step back and protect their privacy."},
            {"title": "Make the area safe", "text": "Move hard, sharp or hot objects away. Don't hold them down and don't move them unless they are in danger."},
            {"title": "Protect the head", "text": "Place something soft under their head, like a folded jacket or towel."},
            {"title": "When the jerking stops", "text": "Roll them onto their side (recovery position) so saliva or vomit can drain. Check they are breathing normally."},
            {"title": "Stay with them", "text": "Reassure them as they wake up. It can take 15-30 minutes to recover fully. Note how long the seizure lasted."},
        ],
        "avoid": [
            "Don't put anything in their mouth.",
            "Don't hold them down or try to stop the jerking.",
            "Don't give food or drink until they are fully alert.",
        ],
        "call_when": [
            "It is their first seizure, or the cause is unknown",
            "It lasts more than 5 minutes, or another follows quickly",
            "They are unresponsive for more than 10 minutes after, or have trouble breathing",
            "It happened in water, or they are injured or pregnant",
        ],
        "checkin": "Has the seizure stopped, and are they waking up and breathing normally?",
        "escalate_if_no": "Seizure not settling or person not recovering",
        "after_care": "People known to have epilepsy often recover without hospital. Otherwise they should see a doctor.",
        "sources": [
            {"name": "St John Ambulance: seizure", "url": "https://www.sja.org.uk/first-aid-advice/seizure/"},
        ],
    },
    # ------------------------------------------------------------ ANAPHYLAXIS
    "anaphylaxis": {
        "icon": "🐝", "title": "Severe allergic reaction", "category": "critical",
        "severity": "critical", "review": "sourced",
        "summary": "Swelling of the face or throat, wheezing or collapse after a sting, food or medicine.",
        "keywords": ["anaphyla", "allerg", "epipen", "auto-injector", "swollen throat", "swelling face", "bee sting", "wasp"],
        "always_escalate": "Severe allergic reaction (anaphylaxis) is life-threatening",
        "triage": [
            {"q": "Has the person collapsed or stopped responding?",
             "flag": "Allergic reaction with collapse", "switch": "cpr"},
        ],
        "steps": [
            {"title": "Call now", "text": "Call 112 / 108 and say 'severe allergic reaction'."},
            {"title": "Use the auto-injector", "text": "If they have an adrenaline auto-injector (EpiPen or similar), use it straight away as instructed on the device, into the outer thigh. Any available auto-injector may be used."},
            {"title": "Position them", "text": "Lie them down with their legs raised. If they are struggling to breathe, let them sit up instead. Don't let them stand or walk."},
            {"title": "Second dose", "text": "If there is no improvement after 5 minutes, or symptoms return, a second auto-injector can be given. Check with the emergency operator."},
            {"title": "Watch closely", "text": "Monitor breathing and responses until the ambulance arrives. If they become unresponsive and stop breathing normally, start CPR."},
        ],
        "avoid": [
            "Don't let them stand or walk about.",
            "Don't wait to see if it passes. Use the auto-injector first.",
            "Don't give food, drink or tablets by mouth if they have trouble breathing or swallowing.",
        ],
        "call_when": ["Always. Even if they improve after the injection, they need hospital care."],
        "after_care": "Everyone who has received adrenaline must go to hospital, because symptoms can return.",
        "sources": [
            {"name": "St John Ambulance: anaphylaxis", "url": "https://www.sja.org.uk/first-aid-advice/anaphylaxis/"},
        ],
    },
    # ----------------------------------------------------------------- ASTHMA
    "asthma": {
        "icon": "🫁", "title": "Asthma attack", "category": "medical",
        "severity": "urgent", "review": "sourced",
        "summary": "Wheezing, tight chest, struggling to breathe or speak.",
        "keywords": ["asthma", "wheez", "inhaler", "cant breathe", "can't breathe", "short of breath", "breathless", "difficulty breathing"],
        "triage": [
            {"q": "Is the person too breathless to speak in full sentences, or turning blue or grey around the lips?",
             "flag": "Severe breathing difficulty"},
            {"q": "Is there no inhaler available?", "flag": "No reliever inhaler available"},
        ],
        "steps": [
            {"title": "Sit upright", "text": "Help them sit up straight and stay calm. Don't let them lie down."},
            {"title": "Reliever inhaler", "text": "Blue reliever inhaler: 1 puff every 30-60 seconds, up to 10 puffs, shaking it between puffs and using a spacer if they have one. If they have a combined AIR or MART inhaler, 1 puff every 1-3 minutes, up to 6 puffs. If their asthma action plan says otherwise, follow the plan.", "timer": 60},
            {"title": "Still not better?", "text": "If they feel worse at any point, or are no better after the maximum puffs, call 112 / 108."},
            {"title": "Wait and repeat", "text": "If help hasn't arrived and symptoms are no better after 10 minutes, use the inhaler again up to the same maximum, and call again."},
        ],
        "avoid": [
            "Don't let them lie down.",
            "Don't leave them alone.",
            "Don't be afraid to call for help.",
        ],
        "checkin": "After the inhaler, is the person's breathing clearly easier?",
        "escalate_if_no": "Asthma attack not responding to the reliever inhaler",
        "call_when": [
            "They feel worse at any point",
            "No improvement after the maximum puffs",
            "They don't have an inhaler",
        ],
        "after_care": "Even if they recover, they need a same-day review by a doctor.",
        "sources": [
            {"name": "NHS: asthma attacks", "url": "https://www.nhs.uk/conditions/asthma/"},
        ],
    },
    # -------------------------------------------------------------- SNAKEBITE
    "snakebite": {
        "icon": "🐍", "title": "Snakebite", "category": "india",
        "severity": "critical", "review": "sourced",
        "summary": "Every snakebite is an emergency in India. Keep still and go to a hospital with antivenom.",
        "keywords": ["snake", "cobra", "krait", "viper", "venom", "bitten by a snake", "snakebite"],
        "always_escalate": "Every snakebite needs hospital care (antivenom may be needed)",
        "triage": [
            {"q": "Any drooping eyelids, double vision, trouble speaking, swallowing or breathing, or bleeding from the gums or the bite?",
             "flag": "Signs of serious venom effects"},
            {"q": "Has the person collapsed or stopped responding?",
             "flag": "Snakebite victim is unresponsive", "switch": "cpr"},
        ],
        "steps": [
            {"title": "Reassure", "text": "Move away from the snake. Don't try to catch or kill it. Calm the person: panic speeds up the spread of venom. Tell them help is available."},
            {"title": "Keep them still", "text": "Lay them down and keep the bitten limb as still as possible. Don't let them walk. Movement spreads venom faster."},
            {"title": "Remove tight items", "text": "Gently remove rings, bangles, watches and tight clothing near the bite before swelling begins."},
            {"title": "Immobilise the limb", "text": "Splint or sling the bitten limb in the same way as a broken limb. Keep it comfortable but do NOT wrap it tightly."},
            {"title": "Go to hospital now", "text": "Get to a hospital with antivenom as fast as possible. Call 108 or use any quick transport, and carry the person rather than letting them walk. Tell the doctors the time of the bite and any symptoms. A photo of the snake from a safe distance helps, but don't waste time."},
            {"title": "Watch the breathing", "text": "Keep checking breathing and responses on the way. If breathing stops, start CPR."},
        ],
        "avoid": [
            "Don't apply a tourniquet or tight bandage. Indian national guidance rejects both.",
            "Don't cut the bite, suck out venom, or apply ice, herbs or chemicals.",
            "Don't delay going to hospital to visit a traditional healer. They have no proven benefit.",
            "Don't give alcohol or home remedies.",
        ],
        "call_when": ["Always. Even if there are no symptoms yet, venom effects can be delayed for hours."],
        "after_care": "Keep the person still and monitored until a doctor takes over. No symptoms in the first hour does not mean it is safe.",
        "notes": "The Indian national snakebite protocol (R.I.G.H.T.: Reassure, Immobilise, Get to Hospital, Tell the doctor) rejects tourniquets and pressure-immobilisation bandages, unlike Australian guidance. One non-official website recommended a tight pressure bandage; it contradicts the national protocol and was deliberately NOT used.",
        "sources": [
            {"name": "Indian Pediatrics: national snakebite protocol", "url": "https://indianpediatrics.net/mar2007/mar-173-176.htm"},
            {"name": "Indian protocols for snakebite (review)", "url": "https://vjim.org/?p=4570"},
        ],
    },
    # ------------------------------------------------------------- ANIMAL BITE
    "animal_bite": {
        "icon": "🐕", "title": "Dog / animal bite", "category": "india",
        "severity": "urgent", "review": "sourced",
        "summary": "Wash for 15 minutes, then get rabies vaccination advice. Do this even if the dog seemed healthy.",
        "keywords": ["dog bite", "dog bit", "bitten by dog", "monkey", "cat bite", "scratch", "rabies", "stray dog", "animal bite", "bitten by a dog"],
        "triage": [
            {"q": "Is the bite bleeding heavily, or on the face, head or neck?",
             "flag": "Serious animal bite"},
            {"q": "Was it a stray, an unknown animal, or one acting strangely?", "flag": "Possible rabid animal"},
        ],
        "steps": [
            {"title": "Wash straight away", "text": "Wash the wound thoroughly with soap (detergent is fine) and running water for at least 15 minutes. If there is no soap, use running water alone. If eyes or mouth were exposed, rinse them well with water.", "timer": 900},
            {"title": "Don't wash if bleeding heavily", "text": "If the bite is bleeding heavily, press on it with a clean cloth first (see the heavy bleeding guide), then get help."},
            {"title": "Keep it open and clean", "text": "Keep the wound uncovered if possible, or cover very loosely with clean gauze. Don't stitch or tightly bandage it."},
            {"title": "See a doctor today", "text": "Go to a hospital or anti-rabies clinic right away, even for a small bite or scratch. Anti-rabies vaccination, and for bleeding bites also rabies immunoglobulin, must be started as soon as possible. Note the animal's details if known."},
        ],
        "avoid": [
            "Don't apply haldi (turmeric), oil, chilli, lime or other home remedies.",
            "Don't ignore a bite because the animal 'looked healthy' or is a pet.",
            "Don't tightly bandage or suture the wound.",
        ],
        "call_when": [
            "Heavy bleeding, or a bite to the face, head or neck",
            "Any bite that breaks the skin: see a doctor the same day for rabies vaccination",
        ],
        "after_care": "Rabies is almost always fatal once symptoms appear, but it is preventable if vaccination starts promptly. Complete every dose the doctor prescribes.",
        "sources": [
            {"name": "National rabies guidance: summary (JSS Hospital)", "url": "https://jsshospital.in/rabies-a-fatal-but-preventable-disease-be-informed-and-keep-others-informed/"},
            {"name": "National Rabies Control Programme (MoHFW)", "url": "https://rabiesfreeindia.mohfw.gov.in/downloads"},
        ],
    },
    # --------------------------------------------------------------- FRACTURE
    "fracture": {
        "icon": "🦴", "title": "Broken bone / sprain", "category": "injury",
        "severity": "moderate", "review": "sourced",
        "summary": "Pain, swelling or an odd shape after a fall or twist.",
        "keywords": ["fractur", "broke", "broken", "sprain", "twist", "ankle", "wrist", "dislocat", "bone$"],
        "triage": [
            {"q": "Is a bone visible, is the limb clearly bent out of shape, or is there heavy bleeding?",
             "flag": "Possible open or severe fracture"},
            {"q": "Is the injury to the head, neck or back, or after a fall from a height or road accident?",
             "flag": "Possible head or spine injury. Do not move the person"},
            {"q": "Are the fingers or toes beyond the injury cold, pale, blue or numb?",
             "flag": "Possible circulation or nerve damage"},
        ],
        "steps": [
            {"title": "Support the injury", "text": "Help them hold the injury with their own hand, or use a cushion or clothing to stop it moving. Support the limb above and below the injury if you can. Don't move it more than necessary."},
            {"title": "Don't straighten it", "text": "If the limb looks bent or a joint looks out of place, leave it. Never try to push a bone or joint back. If you can, place soft padding such as clothing or blankets around the limb, but don't force it."},
            {"title": "Cover any wound", "text": "If the skin is broken, cover the wound with a clean dressing. If bleeding is heavy, follow the heavy bleeding guide."},
            {"title": "Get medical help", "text": "Take them to hospital, or send them with someone. If they can't move by themselves or are in a lot of pain, call 108 or 112."},
            {"title": "Keep supporting", "text": "Keep supporting the injury until they receive medical help."},
        ],
        "avoid": [
            "Don't move the person if a neck or back injury is possible.",
            "Don't try to push a bone or joint back into place.",
            "Don't assume it is not broken because they can move the limb or stand on it. Only an X-ray can tell.",
        ],
        "checkin": "Is the pain mild, with normal movement and no obvious deformity?",
        "escalate_if_no": "Severe pain or loss of movement can mean a fracture and needs an X-ray",
        "call_when": [
            "A bone is visible, the limb is deformed, or bleeding is heavy",
            "Neck, back or head injury, or a fall from a height",
            "Fingers or toes beyond the injury are cold, pale, blue or numb",
            "The person can't move by themselves or is in a lot of pain",
        ],
        "after_care": "A broken bone, sprain or strain usually can't be told apart without an X-ray. If you are in any doubt, or the pain does not improve, get medical advice.",
        "notes": "Steps follow the British Red Cross broken bone page (support the injury, get to hospital, keep supporting). Splinting and ice were removed because that page does not tell bystanders to splint or use cold packs. The 'cover any wound' step is general practice, linked from the Red Cross heavy bleeding guidance. Emergency numbers changed to India (108/112). Not clinically reviewed.",
        "sources": [
            {"name": "British Red Cross: first aid for a broken bone", "url": "https://www.redcross.org.uk/first-aid/learn-first-aid/broken-bone"},
        ],
    },
    # --------------------------------------------------------------- CHEMICAL
    "chemical": {
        "icon": "🧪", "title": "Chemical / pesticide splash", "category": "india",
        "severity": "urgent", "review": "sourced",
        "summary": "Acid, bleach, pesticide or other chemical on skin or in the eyes.",
        "keywords": ["chemical", "acid", "bleach", "pesticide", "insecticide", "splash", "caustic", "alkali", "fumes"],
        "triage": [
            {"q": "Did the chemical get into the eyes?", "flag": "Chemical in the eye"},
            {"q": "Was any swallowed, or is the person coughing or struggling to breathe from fumes?",
             "flag": "Swallowed chemical or fume inhalation"},
        ],
        "steps": [
            {"title": "Protect yourself", "text": "Wear gloves if you can and avoid touching the chemical. If there are fumes, open windows or move the person outside. If it is safe, seal the container."},
            {"title": "Brush off powder", "text": "If the chemical is a dry powder, gently brush it off the skin first, then flood with water."},
            {"title": "Flood with water", "text": "Flood the skin with cool or lukewarm running water for at least 20 minutes. Pour it away from yourself, and don't let contaminated water pool under or spread over clean skin.", "timer": 1200},
            {"title": "Remove contaminated clothes", "text": "While flushing, carefully remove contaminated clothing and jewellery. Cut it off rather than pulling it over the face."},
            {"title": "If it is in the eye", "text": "Hold the eye under gently running cool water for at least 10 minutes, with the injured eye lower so water doesn't run into the other eye. Don't let them touch or rub it. Don't force out a contact lens. Then cover loosely with a clean, non-fluffy pad.", "timer": 600},
            {"title": "Get help and the label", "text": "Call 112 / 108. Keep the container or label to show the doctors so they know the chemical."},
        ],
        "avoid": [
            "Don't try to neutralise a chemical with another chemical (like vinegar on alkali).",
            "Don't make a person vomit if they swallowed a chemical.",
            "Don't rub the eyes or skin.",
            "Don't touch your own face while wearing contaminated gloves.",
        ],
        "checkin": "After flushing, is the pain easing with no blistering, vision problems or trouble breathing?",
        "escalate_if_no": "Chemical injuries that don't settle need urgent medical care",
        "call_when": [
            "Any chemical in the eye, or a burn that blisters or covers a large area",
            "Chemical swallowed, or breathing problems from fumes",
            "Burn on the face, hands, feet, groin or a major joint",
        ],
        "after_care": "St John Ambulance says anyone with a chemical burn needs medical help. Pesticide exposure can cause delayed symptoms, so get checked even if you feel fine.",
        "sources": [
            {"name": "St John Ambulance: chemical burns", "url": "https://www.sja.org.uk/get-advice/first-aid-advice/burns-and-scalds/chemical-burns/"},
            {"name": "healthdirect Australia: chemical burns", "url": "https://healthdirect.gov.au/chemical-burns"},
        ],
    },
    # ------------------------------------------------------------- HEATSTROKE
    "heatstroke": {
        "icon": "🌡️", "title": "Heat exhaustion / heatstroke", "category": "india",
        "severity": "urgent", "review": "sourced",
        "summary": "Very hot, dizzy, sweating heavily, or confused and not sweating after time in the heat.",
        "keywords": ["heatstroke", "heat stroke", "sunstroke", "heat exhaustion", "overheat", "too hot", "dizzy in the sun", "in the sun", "not sweating", "hot and dry", "heat$"],
        "triage": [
            {"q": "Is the skin hot and dry (not sweating), or is the person confused or uncoordinated?",
             "flag": "Possible heatstroke: medical emergency"},
        ],
        "steps": [
            {"title": "Move to a cool place", "text": "Get them out of the sun into the shade or a cool room. Loosen or remove extra clothing."},
            {"title": "Give fluids", "text": "If they are awake and can swallow, give plenty of cool water, ideally an oral rehydration solution (ORS) or sports drink.", "tool": None},
            {"title": "Cool their skin", "text": "Spray or sponge them with cool water and fan them. For suspected heatstroke, wrap them in a cool, wet sheet and keep fanning while you wait for help.", "timer": 1800},
            {"title": "Reassess in 30 minutes", "text": "Heat exhaustion usually improves within 30 minutes of cooling. If they are not improving, or the signs of heatstroke appear, it is an emergency."},
        ],
        "avoid": [
            "Don't give fluids to someone who is confused, drowsy or can't swallow safely.",
            "Don't leave them in the sun or a hot vehicle.",
            "Don't use ice-cold water baths unless trained.",
        ],
        "checkin": "After 30 minutes in a cool place with fluids, is the person clearly better?",
        "escalate_if_no": "Not recovering after cooling",
        "call_when": [
            "Hot skin that is not sweating",
            "Confusion or lack of coordination",
            "Still unwell after 30 minutes of cooling and drinking fluids",
        ],
        "after_care": "Children, older people and people with long-term conditions are at higher risk. Rest and keep drinking fluids for the rest of the day.",
        "sources": [
            {"name": "NHS: heat exhaustion and heatstroke", "url": "https://www.nhs.uk/conditions/heat-exhaustion-heatstroke/"},
        ],
    },
    # --------------------------------------------------------- ELECTRIC SHOCK
    "electric": {
        "icon": "🔌", "title": "Electric shock", "category": "injury",
        "severity": "urgent", "review": "sourced",
        "summary": "Contact with a live wire, socket or power line. Don't touch them until power is off.",
        "keywords": ["electric", "shock", "electrocut", "live wire", "power line", "socket", "current"],
        "always_escalate": "Electric shock can affect the heart even if the person looks fine",
        "triage": [
            {"q": "Is the person still touching the electrical source, or is there a downed power line nearby?",
             "flag": "Ongoing electrical danger"},
            {"q": "Has the person collapsed or stopped breathing?",
             "flag": "Collapse after electric shock", "switch": "cpr"},
        ],
        "steps": [
            {"title": "Don't touch them yet", "text": "Do NOT touch the person while they may still be in contact with electricity, or you could be shocked too. Call 108 or 112 for help."},
            {"title": "Turn off the power", "text": "Turn off the source of electricity at the switch or mains to break the contact, if you can do it safely."},
            {"title": "Or move them away", "text": "If you can't switch it off, stand on dry insulating material (a plastic mat or wooden box) and use a broom handle or wooden pole to push the person's limb away from the source. If that doesn't work, loop rope under their arms or around their ankles and pull them away. Don't touch them."},
            {"title": "Check once it is safe", "text": "Once you are sure contact is broken, check if they respond and are breathing normally. If not breathing normally, start CPR. Then treat any injuries."},
            {"title": "Cool any burns", "text": "Cool burns under cool running water for at least 20 minutes and cover loosely with cling film.", "timer": 1200},
            {"title": "Get checked", "text": "Everyone who has had an electric shock should be checked by a doctor, because it can affect the heart even if they feel fine."},
        ],
        "avoid": [
            "Don't touch the person or the source until the power is off.",
            "Don't go near downed high-voltage lines. Stay far away and wait for the power company or fire service to cut the power.",
            "Don't use anything wet or metal to move the source.",
        ],
        "call_when": ["Always, especially for high voltage, lightning, or power lines."],
        "after_care": "Medical assessment is advised for every electric shock, even a mild one.",
        "notes": "Steps 1-4 follow St John Ambulance UK (electric shock, clinically reviewed April 2025). High-voltage warning and 'seek medical aid even after a mild shock' follow St John Ambulance NSW. The burn-cooling step reuses the burns guidance (20 min). The UK page covers low-voltage shock only. Not clinically reviewed.",
        "sources": [
            {"name": "St John Ambulance: electric shock", "url": "https://www.sja.org.uk/first-aid-advice/electrocution/"},
            {"name": "St John Ambulance NSW: how to respond to an electric shock", "url": "https://stjohnnsw.com.au/guides-electric-shock"},
        ],
    },
}

# Phrases in free text that mean "act now", whatever else the person says.
# They bypass the language model completely so the alarm never depends on a network call.
URGENT_PATTERNS = [
    (r"not breathing|stopped breathing|isn'?t breathing|no pulse|cardiac arrest|heart stopped|stopped moving", "cpr"),
]


def public_topic(topic_id):
    """Small summary of a topic for the home screen."""
    t = TOPICS[topic_id]
    return {
        "id": topic_id, "icon": t["icon"], "title": t["title"], "summary": t["summary"],
        "category": t["category"], "severity": t["severity"],
    }