"""Score human answers to labelling-page Set D (which vehicle? 2019-2023 stories) against NEISS-AI.

The answer key (NEISS-AI's device label and whether rules or the text classifier decided it) is kept
private and is NOT in this repository, so the set stays blind. Usage:

    python validation/score_set_d.py reviewer_labels.csv path/to/set_d_KEY.csv

Reports agreement on the full 4-way answer, on 'e-bike or not', Cohen's kappa, and agreement on the
stories the text classifier decided (the ones a human check matters most for).
"""
from __future__ import annotations

import csv
import math
import sys
from collections import Counter

MAP = {"E-bike": "e-bike", "Bicycle": "bicycle", "E-scooter": "e-scooter"}


def kappa(pairs):
    n = len(pairs)
    if not n:
        return float("nan")
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


def wilson(k, n, z=1.96):
    if not n:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - h) / d, (c + h) / d


def main(labels, keyfile):
    key = {r["CPSC_Case_Number"]: r for r in csv.DictReader(open(keyfile, newline=""))}
    ans = {r["case_number"]: r["device"].strip().lower() for r in csv.DictReader(open(labels, newline=""))
           if r.get("set") == "D" and r.get("device", "").strip()}
    rows = [(MAP.get(key[i]["dev"], "other"), a, key[i]["label_source"]) for i, a in ans.items() if i in key]
    print(f"Answered: {len(rows)} of {len(key)} stories")
    for name, sub in (("All stories", rows), ("Classifier-decided", [r for r in rows if r[2] == "classifier"]),
                      ("Rule-decided", [r for r in rows if r[2] != "classifier"])):
        k = sum(t == h for t, h, _ in sub)
        lo, hi = wilson(k, len(sub))
        eb = [("e-bike" if t == "e-bike" else "not", "e-bike" if h == "e-bike" else "not") for t, h, _ in sub]
        ke = sum(a == b for a, b in eb)
        print(f"{name}: same answer {k}/{len(sub)} = {100 * k / max(len(sub), 1):.1f}% (95% CI {100 * lo:.1f}-{100 * hi:.1f}); "
              f"e-bike or not {ke}/{len(sub)}; kappa {kappa([(t, h) for t, h, _ in sub]):.2f}")
    print("Tool vs human (rows = tool):", Counter((t, h) for t, h, _ in rows).most_common())


if __name__ == "__main__":
    main(*sys.argv[1:3])
