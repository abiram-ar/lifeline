# LifeLine photo add-on

Upload or take a photo (e.g. a bike crash). The AI **describes what is visible**, you confirm it, and
**fixed rules** open the right guide. For a crash: do not move them, leave the helmet on, call 112/108, wait.

## Install (3 steps, Windows)
1. Stop the server (Ctrl+C). Copy these files into your `lifeline` folder, keeping the `static` and `tests` folders:
   `vision.py  trauma.py  photo_api.py  apply_addon.py` (main folder),
   `static/photo.js  static/photo.css`, `tests/test_photo.py`.
2. In a terminal inside the `lifeline` folder run: `python apply_addon.py`
   (adds 2 lines to `server.py` and 2 tags to `static/index.html`, and keeps `.bak` backups).
3. `python server.py`, then refresh the browser with Ctrl+Shift+R.

Check the vision model works: open **http://localhost:8000/api/photo/health?test=1**
(`"ok": true` = working; otherwise it shows the exact error).
Run tests: `python -m unittest discover -s tests -v`

## How it works
```
photo --(browser shrinks it to 1024px, strips camera data)--> /api/photo
   --> vision.py asks Groq (qwen/qwen3.8-27b) to fill a FIXED form: scene, person lying?, vehicle?, helmet?, bleeding?...
   --> answers are validated (anything unexpected becomes "unclear")
   --> route() = fixed rules pick the protocol (crash/fall -> "Road crash / serious fall", burn, chemical, ...)
   --> user sees "What I can see" and confirms --> the normal step-by-step guide starts
```
Safety: the AI never diagnoses and never writes advice. A photo can't show a spine injury, so any crash or fall
scene opens the "assume the worst" guide. Unclear photos ask the user to describe it instead of guessing.

## Limits (say these in your report)
- The AI can misread a photo (wrong scene, missed bleeding). That's why the user confirms before the guide starts.
- The photo is sent to Groq for analysis. LifeLine does not save it. Don't upload photos with faces or private details you don't need.
- Needs the Groq key and internet. Without them the photo buttons explain this and the rest of the app still works.
- Groq's vision model was replaced in 2026 (Llama 4 Scout retired 17 July). If `qwen/qwen3.8-27b` is retired too, set
  `GROQ_VISION_MODEL=newmodel` in `.env`.
- The new "Road crash / serious fall" protocol is marked **"Awaiting expert review"**: it rests on secondary sources
  (Mayo Clinic citing the American Red Cross, a BHS/SkillBase fact sheet, Hong Kong Red Cross/St John via a news article).
  Compare it with the British Red Cross / St John Ambulance spinal-injury pages before relying on it.
