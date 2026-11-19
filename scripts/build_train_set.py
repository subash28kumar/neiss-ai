"""Build Set C ("Help train") for the labelling page: the e-bike stories NEISS-AI finds hardest.

Deterministic: no randomness. Stories are scored for how close a call they are, sorted by that
score and then by story id, and the top ones are kept. Spot-check stories with clear answers are
mixed in (one after every 9 hard stories) so careless or bad answers can be detected.

Writes
  validation/learning/set_c_items.csv      story id, text, why it is hard (or "spot check")
  validation/learning/set_c_spotcheck.csv  known answers for the spot-check stories
and returns the Set C entry used by scripts/build_label_sets.py.

Stories in the locked validation sets are never included.

    python scripts/build_train_set.py
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from neissai.circumstances import UNK, VEH, helmet, motor_vehicle  # noqa: E402
from neissai.ebike_type import ebike_type  # noqa: E402
from neissai.learn import locked_ids, norm_text, story_id  # noqa: E402

N_HARD = 200
N_SPOT = 22
SPOT_EVERY = 9
MAX_LEN = 320
OUT = ROOT / "validation" / "learning"

MPH = re.compile(r"\b(\d{1,3})\s*(?:-\s*\d{1,3}\s*)?MPH\b")
GUESS = re.compile(r"\b(?:THOUGHT|ESTIMAT\w*|APPROX\w*|ABOUT|AROUND|PROBABLY|MAYBE|POSSIBLY|BELIEVE[SD]?)\b[^.;]{0,25}\b\d{1,3}\s*MPH")
MOTORISH = re.compile(r"\b(?:MOTORI[SZ]ED|MOTOR\s*BIKE|MOTORBIKE|DIRT\s*BIKE|MOPED|SCOOTER)\b")
VEHWORD = re.compile(rf"\b{VEH}\b")
AVOID = re.compile(r"\bAVOID\w*\b")
BRAND = re.compile(r"\b(?:SUR-?\s?RON|SURRON|TALARIA)\b")
EBIKE_WORD = re.compile(r"\b(?:E-?BIKE|ELECTRIC\s+BI(?:KE|CYCLE))\b")
CLEAR_MV = re.compile(rf"\b(?:STRUCK|HIT)\s+BY\s+(?:A\s+)?(?:CAR|TRUCK|VEHICLE|SUV|VAN)\b")
CLEAR_HELMET = re.compile(r"\b(?:WEARING\s+(?:A\s+|HIS\s+|HER\s+)?HELMET|NO\s+HELMET|WITHOUT\s+(?:A\s+)?HELMET)\b")


def before_dx(text: str) -> str:
    return re.split(r"\bDX\b", text, maxsplit=1)[0]


def hardness(text: str) -> tuple[int, list[str]]:
    """Score how close a call a story is (higher = harder) and say why."""
    t = before_dx(text)
    score, why = 0, []
    et = ebike_type(text)
    if et == "unclear":
        score += 3; why.append("e-bike type unclear")
    if et == "likely e-moto":
        score += 1; why.append("called e-moto")
    speeds = [int(m.group(1)) for m in MPH.finditer(t)]
    if any(20 <= s <= 40 for s in speeds):
        score += 2; why.append("speed near the 28 mph line")
    if GUESS.search(t):
        score += 2; why.append("speed is a guess")
    if MOTORISH.search(t):
        score += 1; why.append("motor-type wording")
    mv = motor_vehicle(text)
    if VEHWORD.search(t) and not mv:
        score += 2; why.append("vehicle mentioned, counted as no crash")
    if AVOID.search(t):
        score += 2; why.append("avoiding something")
    if "HELMET" in t and helmet(text) == "not mentioned" and not UNK.search(t):
        score += 2; why.append("helmet mentioned but unclear")
    return score, why


def spot_answer(text: str) -> dict | None:
    """Known answers for a clear-cut story, or None if any question is not clear."""
    t = before_dx(text)
    et = ebike_type(text)
    if BRAND.search(t):
        e = "likely e-moto" if et == "likely e-moto" else None
    elif et == "regular e-bike" and EBIKE_WORD.search(t) and not MPH.search(t) and not MOTORISH.search(t):
        e = "regular e-bike"
    else:
        e = None
    mv = motor_vehicle(text)
    if mv and CLEAR_MV.search(t):
        m = "yes"
    elif not mv and not VEHWORD.search(t) and not AVOID.search(t):
        m = "no"
    else:
        m = None
    h = helmet(text)
    if h in ("yes", "no") and CLEAR_HELMET.search(t):
        hl = h
    elif h == "not mentioned" and "HELMET" not in text.upper():
        hl = "not mentioned"
    else:
        hl = None
    if e and m and hl:
        return {"mv": m, "helmet": hl, "etype": e}
    return None


def train_set(write: bool = True) -> dict:
    data = ROOT / "docs" / "data"
    R = json.loads((data / "records.json").read_text())
    S = json.loads((data / "stories.json").read_text())
    eb = R["devices"].index("E-bike")
    locked = locked_ids()
    stories = {}
    for i, d in enumerate(R["d"]):
        if d != eb or len(S[i]) > MAX_LEN:
            continue
        sid = story_id(S[i])
        if sid not in locked:
            stories.setdefault(sid, norm_text(S[i]))

    hard, spots = [], []
    for sid in sorted(stories):
        txt = stories[sid]
        sc, why = hardness(txt)
        if sc >= 2:
            hard.append((-sc, sid, why))
        elif sc == 0 and len(txt) <= 220:
            a = spot_answer(txt)
            if a:
                spots.append((sid, a))
    hard = sorted(hard)[:N_HARD]

    groups = {}
    for sid, a in spots:  # balance the spot checks across answer types, in id order
        groups.setdefault((a["mv"], a["helmet"], a["etype"]), []).append((sid, a))
    picked, keys = [], sorted(groups)
    while len(picked) < N_SPOT and any(groups[k] for k in keys):
        for k in keys:
            if groups[k] and len(picked) < N_SPOT:
                picked.append(groups[k].pop(0))

    items, rows = [], []
    spot_iter = iter(picked)
    for n, (neg, sid, why) in enumerate(hard, 1):
        items.append({"id": sid, "text": stories[sid]})
        rows.append({"id": sid, "kind": "hard", "score": -neg, "why": "; ".join(why), "text": stories[sid]})
        if n % SPOT_EVERY == 0:
            s = next(spot_iter, None)
            if s:
                items.append({"id": s[0], "text": stories[s[0]]})
                rows.append({"id": s[0], "kind": "spot check", "score": 0, "why": "", "text": stories[s[0]]})
    for s in spot_iter:  # any left over go at the end
        items.append({"id": s[0], "text": stories[s[0]]})
        rows.append({"id": s[0], "kind": "spot check", "score": 0, "why": "", "text": stories[s[0]]})

    if write:
        OUT.mkdir(parents=True, exist_ok=True)
        with open(OUT / "set_c_items.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["id", "kind", "score", "why", "text"])
            w.writeheader(); w.writerows(rows)
        with open(OUT / "set_c_spotcheck.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["id", "mv", "helmet", "etype"])
            w.writeheader()
            for sid, a in picked:
                w.writerow({"id": sid, **a})
    return {"id": "C", "title": f"Set C: help train on hard e-bike cases ({len(items)} stories)",
            "questions": ["mv", "helmet", "etype"], "learn": True, "items": items,
            "n_hard": len(hard), "n_spot": len(picked)}


if __name__ == "__main__":
    s = train_set()
    print(f"Set C: {s['n_hard']} hard stories + {s['n_spot']} spot checks = {len(s['items'])}")
