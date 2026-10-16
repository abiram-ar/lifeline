"""
Measure how accurate the photo analysis is.   Run from the lifeline folder:

    python eval_photo.py photos          (the folder must contain your pictures and a labels.csv)

labels.csv has two columns:  filename,expected
  expected = major_trauma | burn | bleeding | snakebite | chemical | fracture | none
  ("none" = no emergency visible, or too unclear: the app SHOULD NOT start a guide)

For every photo it asks Groq to describe it, applies the same fixed rules the app uses,
and compares with your label. Needs your .env with GROQ_API_KEY, and internet.
It writes results.csv so you can study the mistakes. Photos are not saved anywhere by this script.
"""
import base64
import csv
import io
import os
import sys
import time

# read GROQ_API_KEY from .env (same as the server does)
if os.path.exists(".env"):
    for line in open(".env", encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

import trauma  # noqa: F401,E402  (registers the crash protocol)
import vision  # noqa: E402

# Missing one of these is a SAFETY failure, not just a wrong answer.
URGENT = {"major_trauma", "snakebite", "bleeding", "burn", "chemical"}


def to_data_url(path):
    """Shrink to 1024px like the browser does (needs: pip install pillow). Without Pillow, small files are sent as they are."""
    try:
        from PIL import Image, ImageOps
        img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        img.thumbnail((1024, 1024))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=82)
        raw, mime = buf.getvalue(), "image/jpeg"
    except ImportError:
        raw = open(path, "rb").read()
        mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
        if len(raw) > 1_500_000:
            raise RuntimeError("file is large: run  pip install pillow  so it can be shrunk automatically")
    return f"data:{mime};base64," + base64.b64encode(raw).decode()


def main(folder):
    labels_path = os.path.join(folder, "labels.csv")
    if not os.path.exists(labels_path):
        sys.exit(f"Missing {labels_path}. See photos/labels.example.csv for the format.")
    if not os.getenv("GROQ_API_KEY"):
        sys.exit("No GROQ_API_KEY found. Put it in your .env file first.")

    rows = list(csv.DictReader(open(labels_path, encoding="utf-8")))
    results, retried = [], False
    for i, row in enumerate(rows, 1):
        name, expected = row["filename"].strip(), row["expected"].strip()
        path = os.path.join(folder, name)
        got, note, obs = None, "", {}
        try:
            data_url = to_data_url(path)
            while True:
                try:
                    obs, _ = vision.analyse(data_url)
                    break
                except vision.VisionError as e:
                    if "busy" in str(e) and not retried:       # free-tier rate limit: wait once, try again
                        print("  rate limited, waiting 40 s ..."); time.sleep(40); retried = True; continue
                    raise
            got = vision.route(obs)["topic"]
        except Exception as e:                                  # missing file, AI error, ...
            note = str(e)[:80]
        got_label = got or "none"
        ok = (got_label == expected) and not note
        print(f"[{i}/{len(rows)}] {name:24} expected {expected:12} got {got_label:12} {'OK' if ok else 'XX'} {note}")
        results.append({"file": name, "expected": expected, "got": got_label, "ok": ok, "error": note, **obs})
        retried = False
        time.sleep(2)                                           # be gentle with the free quota

    done = [r for r in results if not r["error"]]
    correct = sum(r["ok"] for r in done)
    dangerous_miss = [r for r in done if r["expected"] in URGENT and r["got"] == "none"]
    wrong_guide = [r for r in done if r["expected"] in URGENT and r["got"] not in ("none", r["expected"])]
    false_alarm = [r for r in done if r["expected"] == "none" and r["got"] != "none"]
    crash = [r for r in done if r["expected"] == "major_trauma"]
    crash_found = sum(r["got"] == "major_trauma" for r in crash)

    print("\n================ RESULTS ================")
    print(f"Photos tested ............ {len(done)} (of {len(results)}; {len(results) - len(done)} errors)")
    print(f"Exact topic accuracy ..... {correct}/{len(done)} = {100 * correct / max(1, len(done)):.0f}%")
    print(f"DANGEROUS MISSES ......... {len(dangerous_miss)}  (emergency photo, but no guide opened)")
    print(f"Wrong guide opened ....... {len(wrong_guide)}")
    print(f"False alarms ............. {len(false_alarm)}  (no emergency, but a guide opened)")
    if crash:
        print(f"Crash photos recognised .. {crash_found}/{len(crash)}")
    for title, items in (("Dangerous misses", dangerous_miss), ("Wrong guide", wrong_guide), ("False alarms", false_alarm)):
        for r in items:
            print(f"  {title}: {r['file']} expected {r['expected']} got {r['got']}")

    fields = sorted({k for r in results for k in r})
    with open("results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(results)
    print("\nFull details saved in results.csv. Send me the numbers above and the 'XX' lines to tune the prompt and rules.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "photos")
