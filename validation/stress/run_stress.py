"""Messy-notes stress test (Nov 2026): how well do NEISS-AI's text rules hold up when injury
notes are written differently from NEISS (lower case, other abbreviations, typos, other formats)?

Nothing here changes NEISS-AI or its published numbers. It only measures.

Tests (all deterministic, seed 2026):
  1. E-bike vs e-moto rule on the locked fresh test (240 stories, reference labels).
  2. Motor vehicle and helmet rules on the locked 300-story test.
  3. Device from TEXT ONLY (no CPSC product codes, as in a state's own ER data): 2024-2025 NEISS
     records whose device CPSC coded (reference), 200 each of E-bike, E-scooter, Bicycle and
     200 other micromobility records.
Each test is run on the clean notes and on 6 messy versions.

    python validation/stress/run_stress.py
"""
from __future__ import annotations

import csv
import json
import math
import random
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
import importlib  # noqa: E402

E = importlib.import_module("neissai.ebike_type")
C = importlib.import_module("neissai.circumstances")
D = importlib.import_module("neissai.devices")

SEED = 2026

# ---------------------------------------------------------------- messy versions of a note
SEX = {"M": ["male", "M", "man"], "F": ["female", "F", "woman"]}
AGE = re.compile(r"\b(\d{1,3}) ?(?:YO|Y/O|YR OLD)? ?([MF])(?:EMALE|ALE)?\b")
VARIANTS = [  # (pattern, replacements) - spellings seen in clinical notes outside NEISS
    (r"\bELECTRIC BICYCLE\b", ["ELECTRIC BIKE", "E-BIKE", "EBIKE", "E BIKE", "ELEC BICYCLE"]),
    (r"\bELECTRIC BIKE\b", ["E-BIKE", "EBIKE", "E BIKE", "ELECTRIC BICYCLE", "ELEC BIKE"]),
    (r"\bE-BIKE\b", ["EBIKE", "E BIKE", "ELECTRIC BIKE", "E-BICYCLE"]),
    (r"\bELECTRIC SCOOTER\b", ["E-SCOOTER", "ESCOOTER", "E SCOOTER", "ELEC SCOOTER"]),
    (r"\bE-SCOOTER\b", ["ESCOOTER", "E SCOOTER", "ELECTRIC SCOOTER"]),
    (r"\bBICYCLE\b", ["BIKE", "PUSH BIKE", "BICYCLE"]),
    (r"\bMOTOR VEHICLE\b", ["MV", "CAR", "AUTO"]),
    (r"\bCAR\b", ["AUTO", "VEHICLE", "CAR"]),
    (r"\bPATIENT\b", ["PT", "PATIENT"]),
    (r"\bPT\b", ["PATIENT", "PT"]),
    (r"\bWITHOUT\b", ["W/O", "WITHOUT"]),
    (r"\bWITH\b", ["W/", "WITH"]),
    (r"\bMPH\b", ["MILES PER HOUR", "MPH", "MI/HR"]),
]
DXV = ["DIAGNOSIS:", "IMPRESSION:", "Dx", "ASSESSMENT:"]


def lower(t, rng):
    return t.lower()


def reformat(t, rng):
    """Clinic style: '29 yo male', other diagnosis headers, sentence case."""
    def age(m):
        return f"{m.group(1)} {rng.choice(['yo', 'y/o', 'year old'])} {rng.choice(SEX[m.group(2)])}"
    t = AGE.sub(age, t, count=1)
    t = re.sub(r"\bDX\b\s*:?", lambda m: rng.choice(DXV) + " ", t)
    return t[:1] + t[1:].lower() if rng.random() < 0.5 else t


def variants(t, rng):
    for pat, reps in VARIANTS:
        t = re.sub(pat, lambda m: rng.choice(reps), t)
    return t


def _typo(w, rng):
    i = rng.randrange(len(w) - 1)
    k = rng.randrange(3)
    if k == 0:
        return w[:i] + w[i + 1] + w[i] + w[i + 2:]       # swap two letters
    if k == 1:
        return w[:i] + w[i + 1:]                          # drop a letter
    return w[:i] + w[i] + w[i:]                           # double a letter


def typos(t, rng, rate=0.05):
    return re.sub(r"[A-Za-z]{4,}", lambda m: _typo(m.group(0), rng) if rng.random() < rate else m.group(0), t)


def typos10(t, rng):
    return typos(t, rng, 0.10)


def combined(t, rng):
    return typos(lower(variants(reformat(t, rng), rng), rng), rng)


VERSIONS = {"clean": lambda t, r: t, "lower case": lower, "clinic format": reformat,
            "other spellings": variants, "typos (5% of words)": typos, "typos (10% of words)": typos10,
            "all combined": combined}


def messy(text, name, key):
    rng = random.Random(f"{SEED}|{name}|{key}")
    return VERSIONS[name](text, rng)


# ---------------------------------------------------------------- helpers
def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - h) / d, (c + h) / d


def pct(k, n):
    lo, hi = wilson(k, n)
    return {"right": k, "n": n, "pct": round(100 * k / n, 1), "lo": round(100 * lo, 1), "hi": round(100 * hi, 1)}


def text_device(t):
    """Device from the note ALONE (no product codes), using NEISS-AI's own word lists."""
    u = t.upper()
    kw = lambda p: re.search(D._noncapturing(p), u) is not None  # noqa: E731
    if kw(D.HOVER_WORDS):
        return "Hoverboard"
    if kw(D.ESC_WORDS):
        return "E-scooter"
    if kw(D.E_WORDS):
        return "E-bike"
    if kw(D.MOPED_WORDS):
        return "Moped / minibike"
    if re.search(r"SKATE ?BOARD", u):
        return "Skateboard"
    if re.search(r"SCOOTER", u):
        return "Kick scooter"
    if re.search(r"BIKE|BICYC|CYCLIST", u):
        return "Bicycle"
    return "Other"


# ---------------------------------------------------------------- tests
def load_tests():
    eb = list(csv.DictReader(open(ROOT / "validation/ebike_type_v2/ebike_type_TEST2_240.csv", newline="")))
    ic = list(csv.DictReader(open(ROOT / "validation/injurycoder_test_300.csv", newline="")))
    rec = json.load(open(ROOT / "docs/data/records.json"))
    stories = json.load(open(ROOT / "docs/data/stories.json"))
    devs = rec["devices"]
    yrs = rec["years"]
    pools = {}
    for i in range(rec["n"]):
        if yrs[rec["y"][i]] < 2024:
            continue
        dv = devs[rec["d"][i]]
        g = dv if dv in ("E-bike", "E-scooter", "Bicycle") else "Other micromobility"
        pools.setdefault(g, []).append(i)
    rng = random.Random(SEED)
    dev = []
    for g in ("E-bike", "E-scooter", "Bicycle", "Other micromobility"):
        for i in sorted(rng.sample(pools[g], min(200, len(pools[g])))):
            dev.append({"id": str(i), "text": stories[i], "ref": devs[rec["d"][i]], "group": g})
    return eb, ic, dev


def run():
    eb, ic, dev = load_tests()
    out = {"seed": SEED, "versions": list(VERSIONS), "ebike_type": {}, "motor_vehicle": {}, "helmet": {},
           "device_text_only": {}, "examples": {}}
    norm = lambda s: s.strip().lower()  # noqa: E731
    for v in VERSIONS:
        # 1. e-bike vs e-moto
        k = sum(E.ebike_type(messy(r["narrative"], v, r["id"])) == norm(r["reference_label"]) for r in eb)
        moto_ref = [r for r in eb if norm(r["reference_label"]) == "likely e-moto"]
        km = sum(E.ebike_type(messy(r["narrative"], v, r["id"])) == "likely e-moto" for r in moto_ref)
        out["ebike_type"][v] = {"all": pct(k, len(eb)), "e-moto found": pct(km, len(moto_ref))}
        # 2. motor vehicle + helmet
        kmv = sum(("yes" if C.motor_vehicle(messy(r["narrative"], v, r["cpsc_case_number"])) else "no")
                  == norm(r["motor_vehicle"]) for r in ic)
        mvpos = [r for r in ic if norm(r["motor_vehicle"]) == "yes"]
        ksens = sum(C.motor_vehicle(messy(r["narrative"], v, r["cpsc_case_number"])) for r in mvpos)
        kh = sum(C.helmet(messy(r["narrative"], v, r["cpsc_case_number"])) == norm(r["helmet"]) for r in ic)
        out["motor_vehicle"][v] = {"right": pct(kmv, len(ic)), "crashes found": pct(ksens, len(mvpos))}
        out["helmet"][v] = {"right": pct(kh, len(ic))}
        # 3. device from text only
        res = {}
        for g in ("E-bike", "E-scooter", "Bicycle"):
            rows = [r for r in dev if r["group"] == g]
            kk = sum(text_device(messy(r["text"], v, r["id"])) == g for r in rows)
            res[f"{g} found"] = pct(kk, len(rows))
        called = [r for r in dev if text_device(messy(r["text"], v, r["id"])) == "E-bike"]
        res["E-bike calls right"] = pct(sum(r["ref"] == "E-bike" for r in called), len(called))
        out["device_text_only"][v] = res
    # misses on clean text-only e-bike: why
    miss = [r for r in dev if r["group"] == "E-bike" and text_device(r["text"]) != "E-bike"]
    out["examples"]["e-bike missed from text alone (clean)"] = Counter(text_device(r["text"]) for r in miss).most_common()
    out["examples"]["sample misses"] = [r["text"][:140] for r in miss[:8]]
    out["examples"]["messy samples"] = {v: messy(eb[0]["narrative"], v, eb[0]["id"]) for v in VERSIONS}
    return out


def table(block, cols):
    lines = ["| Version | " + " | ".join(cols) + " |", "|" + "---|" * (len(cols) + 1)]
    for v, d in block.items():
        lines.append(f"| {v} | " + " | ".join(f"{d[c]['pct']}% ({d[c]['lo']}-{d[c]['hi']}), {d[c]['right']}/{d[c]['n']}" for c in cols) + " |")
    return "\n".join(lines)


def main():
    out = run()
    (HERE / "results.json").write_text(json.dumps(out, indent=1) + "\n")
    md = ["# Messy-notes stress test (November 2026)", "",
          "How well NEISS-AI's text rules hold up when injury notes are written differently from NEISS. "
          "Nothing here changes NEISS-AI or its published numbers; it only measures. Deterministic (seed 2026). "
          "Run: `python validation/stress/run_stress.py`.", "",
          "Messy versions: lower case; clinic format ('29 yo male', 'Impression:' instead of 'DX'); other spellings "
          "('EBIKE', 'E BIKE', 'ELEC BIKE', 'W/O', 'AUTO'); typos in 5% or 10% of words (swapped, dropped or doubled letters, "
          "keywords included); and all combined. Ranges are 95% Wilson intervals.", "",
          "## 1. E-bike vs e-moto rule (locked fresh test, 240 stories)", "", table(out["ebike_type"], ["all", "e-moto found"]).replace("| all |", "| right |", 1), "",
          "## 2. Motor vehicle and helmet (locked test, 300 stories)", "",
          table({v: {"motor vehicle right": out["motor_vehicle"][v]["right"], "crashes found": out["motor_vehicle"][v]["crashes found"],
                     "helmet right": out["helmet"][v]["right"]} for v in out["helmet"]}, ["motor vehicle right", "crashes found", "helmet right"]), "",
          "## 3. Device from the note alone (no CPSC product codes, as in a state's own ER data)", "",
          "2024-2025 NEISS records; reference = CPSC's own device code. 200 each of e-bike, e-scooter, bicycle, and 200 other micromobility records.", "",
          table(out["device_text_only"], ["E-bike found", "E-scooter found", "Bicycle found", "E-bike calls right"]), "",
          "E-bike records missed from the note alone (clean), what the note was read as: "
          + ", ".join(f"{k} {n}" for k, n in out["examples"]["e-bike missed from text alone (clean)"]), "",
          "Sample misses:", ""] + [f"- {s}" for s in out["examples"]["sample misses"]] + ["", "Example of one note in every version:", ""] + \
         [f"- **{v}:** {s[:160]}" for v, s in out["examples"]["messy samples"].items()]
    (HERE / "RESULTS.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
