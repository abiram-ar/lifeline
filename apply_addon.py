"""
Connect the photo add-on to your existing LifeLine project (run once).

Usage (from inside the lifeline folder, after copying the add-on files in):
    python apply_addon.py

It makes two tiny edits and keeps backups (server.py.bak, static/index.html.bak):
  1. server.py          -> two lines that attach the photo routes
  2. static/index.html  -> one stylesheet tag and one script tag
Running it twice is harmless.
"""
import os
import shutil
import sys

problems = []


def edit(path, apply):
    if not os.path.exists(path):
        problems.append(f"Can't find {path}. Run this from inside the lifeline folder.")
        return
    text = open(path, encoding="utf-8").read()
    new = apply(text)
    if new is None:
        return
    if new != text:
        if not os.path.exists(path + ".bak"):
            shutil.copy(path, path + ".bak")
        open(path, "w", encoding="utf-8").write(new)
        print(f"updated  {path}")
    else:
        print(f"already done  {path}")


def server(text):
    if "photo_api.setup" in text:
        return text
    anchor = '@app.get("/api/config")'
    if anchor not in text:
        problems.append('server.py: couldn\'t find \'@app.get("/api/config")\'. Add these two lines above your first '
                        '@app.get/@app.post route instead:\n    import photo_api\n    photo_api.setup(app, get_agent, rate_limit)')
        return None
    return text.replace(anchor, "import photo_api  # photo analysis add-on\nphoto_api.setup(app, get_agent, rate_limit)\n\n\n" + anchor, 1)


def index(text):
    if "photo.js" in text:
        return text
    css, js = '<link rel="stylesheet" href="/static/style.css">', '<script src="/static/app.js" defer></script>'
    if css not in text or js not in text:
        problems.append("static/index.html: couldn't find the style.css / app.js tags. Add these yourself:\n"
                        '    <link rel="stylesheet" href="/static/photo.css">   (in <head>)\n'
                        '    <script src="/static/photo.js" defer></script>      (right AFTER the app.js script tag)')
        return None
    text = text.replace(css, css + '\n  <link rel="stylesheet" href="/static/photo.css">', 1)
    return text.replace(js, js + '\n  <script src="/static/photo.js" defer></script>', 1)


for needed in ("vision.py", "trauma.py", "integration.py", "photo_api.py", "static/photo.js", "static/photo.css"):
    if not os.path.exists(needed):
        problems.append(f"Missing {needed}. Copy ALL add-on files into the lifeline folder first (keep the static/ folder).")

edit("server.py", server)
edit(os.path.join("static", "index.html"), index)

if problems:
    print("\nSomething needs your attention:")
    for p in problems:
        print(" -", p)
    sys.exit(1)
print("\nDone. Restart the server (Ctrl+C, then python server.py) and refresh the browser with Ctrl+Shift+R.")
