"""Build docs/data/explain.json for the website's "How NEISS-AI reads a story" section.

Picks real e-bike injury stories from the site data (docs/data/records.json + stories.json,
public CPSC NEISS narratives), runs the tool's own rules and classifier on each one with
neissai.explain, and saves the reasoning. Every label is checked against the label the tool
gave the record; a story whose explanation disagrees is skipped, never shown.

    python scripts/build_explainer.py
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from neissai.classifier import EbikeMopedClassifier  # noqa: E402
from neissai.explain import explain_story  # noqa: E402

MAX_LEN = 320
FEATURED = [  # (chip title, test) - the first matching story (in a fixed random order) is used
    ("Says “e-bike”", lambda x: x["device"]["how"] == "words" and x["type"]["label"] == "regular e-bike"
     and x["helmet"]["label"] == "not mentioned" and not x["mv"]["label"] and len(x["text"]) < 150),
    ("AI decides (before 2024)", lambda x: x["device"]["how"] == "classifier" and x["device"]["p"] > 0.8
     and x["type"]["label"] == "regular e-bike" and len(x["device"]["terms"]) >= 4 and len(x["text"]) < 170),
    ("Too fast for an e-bike", lambda x: x["type"]["label"] == "likely e-moto" and "speed" in x["type"]["why"]
     and not x["mv"]["label"] and "AVOID" not in x["text"] and len(x["text"]) < 220),
    ("No helmet, hit by a car", lambda x: x["helmet"]["label"] == "no" and x["mv"]["label"] and x["mv"]["spans"]
     and x["helmet"]["spans"] and any(w in x["text"] for w in ("STRUCK BY", "HIT BY")) and "AVOID" not in x["text"]
     and len(x["text"]) < 240),
    ("Helmet worn", lambda x: x["helmet"]["label"] == "yes" and x["helmet"]["spans"] and not x["mv"]["label"]
     and len(x["text"]) < 200),
    ("CPSC's e-bike code", lambda x: x["device"]["how"] == "code" and len(x["text"]) < 160),
    ("Unclear wording", lambda x: x["type"]["label"] == "unclear" and x["type"]["spans"] and len(x["text"]) < 220),
]
POOL = {"words": 50, "classifier": 40, "code": 30, "likely e-moto": 20, "unclear": 20}


def build(out_path: Path | None = None, seed: int = 2026) -> dict:
    data = ROOT / "docs" / "data"
    R = json.loads((data / "records.json").read_text())
    S = json.loads((data / "stories.json").read_text())
    years, devices = R["years"], R["devices"]
    eb = devices.index("E-bike")
    idx = [i for i in range(len(S)) if R["d"][i] == eb and len(S[i]) <= MAX_LEN]
    rng = random.Random(seed)
    rng.shuffle(idx)
    clf = EbikeMopedClassifier.load_default()
    featured, pool, seen = [], [], set()
    need = dict(POOL)
    left = list(FEATURED)
    skipped = 0
    for i in idx:
        x = explain_story(S[i], years[R["y"][i]], clf)
        if x["device"]["label"] != "E-bike":  # must agree with the tool's own label
            skipped += 1
            continue
        for k, (title, test) in enumerate(left):
            if test(x):
                featured.append({**x, "title": title}); seen.add(i); left.pop(k)
                break
        if i in seen:
            continue
        key = x["type"]["label"] if x["type"]["label"] in ("likely e-moto", "unclear") else x["device"]["how"]
        if need.get(key, 0) > 0:
            need[key] -= 1; pool.append(x); seen.add(i)
        if not left and not any(need.values()):
            break
    order = [t for t, _ in FEATURED]
    featured.sort(key=lambda f: order.index(f["title"]))
    out = {"updated": R.get("updated"), "featured": featured, "pool": pool,
           "note": "Real NEISS injury stories (public CPSC data), read by NEISS-AI's own rules and classifier."}
    path = out_path or (data / "explain.json")
    path.write_text(json.dumps(out, separators=(",", ":")))
    return {"path": str(path), "featured": len(featured), "pool": len(pool), "skipped": skipped}


if __name__ == "__main__":
    print(build())
