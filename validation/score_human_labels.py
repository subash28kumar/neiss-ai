"""Score labels from an outside human reviewer (the CSV from docs/label.html).

Compares the reviewer's answers with (1) NEISS-AI's own answers and (2) the existing answer
key, for every story the reviewer labelled. Prints agreement and Cohen's kappa with 95% CIs.

    python validation/score_human_labels.py reviewer_labels.csv
"""
from __future__ import annotations

import csv
import importlib
import math
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
C = importlib.import_module("neissai.circumstances")
E = importlib.import_module("neissai.ebike_type")

NORM = {"yes": "yes", "no": "no", "not mentioned": "not mentioned", "regular e-bike": "regular e-bike",
        "likely e-moto": "likely e-moto", "unclear": "unclear", "true": "yes", "false": "no"}


def norm(v):
    return NORM.get(str(v).strip().lower(), str(v).strip().lower())


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"),) * 2
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - h) / d, (c + h) / d


def kappa(a, b):
    n = len(a)
    if n == 0:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


def load_reference():
    ref = {}
    with open(HERE / "injurycoder_test_300.csv", newline="") as f:
        for r in csv.DictReader(f):
            t = r["narrative"]
            ref[("A", r["cpsc_case_number"])] = {
                "text": t, "mv_key": norm(r["motor_vehicle"]), "helmet_key": norm(r["helmet"]),
                "mv_tool": "yes" if C.motor_vehicle(t) else "no", "helmet_tool": C.helmet(t)}
    with open(HERE / "ebike_type_v2" / "ebike_type_TEST2_240.csv", newline="") as f:  # fresh locked test (rule v2)
        for r in csv.DictReader(f):
            ref[("B", r["id"])] = {
                "text": r["narrative"], "etype_key": norm(r["reference_label"]), "etype_tool": E.ebike_type(r["narrative"])}
    return ref


def score(path):
    ref = load_reference()
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    who = {(r.get("labeler", ""), r.get("organization", "")) for r in rows}
    print(f"File: {path}\nReviewer(s): {sorted(who)}\nRows: {len(rows)}\n")
    for field in ("mv", "helmet", "etype"):
        pairs = [(norm(r[field]), ref[(r["set"], r["case_number"])]) for r in rows
                 if r.get(field) and (r["set"], r["case_number"]) in ref and f"{field}_tool" in ref[(r["set"], r["case_number"])]]
        if not pairs:
            continue
        human = [p[0] for p in pairs]
        for other in ("tool", "key"):
            o = [p[1][f"{field}_{other}"] for p in pairs]
            k = sum(h == x for h, x in zip(human, o)); lo, hi = wilson(k, len(o))
            name = "NEISS-AI" if other == "tool" else "existing answer key"
            print(f"{field:7s} vs {name:20s} agree {k}/{len(o)} = {k / len(o):.1%} "
                  f"(95% CI {lo:.1%}-{hi:.1%}), kappa {kappa(human, o):.2f}")
        dis = [(p[0], p[1][f"{field}_tool"], p[1]["text"][:110]) for p in pairs if p[0] != p[1][f"{field}_tool"]]
        for h, t, s in dis[:15]:
            print(f"   reviewer={h!r:18s} NEISS-AI={t!r:18s} {s}")
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for p in sys.argv[1:]:
        score(p)
