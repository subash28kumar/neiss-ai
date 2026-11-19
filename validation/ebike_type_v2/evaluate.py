"""Score the e-bike/e-moto rule once on the fresh locked test (240 stories), v2.

Weighted back to all e-bike stories with the sampling-group sizes (population.json), with a
bootstrap 95% CI (resampling within groups, fixed seed 2026 so results are reproducible).
Also scores the previous rule (v1.4) on the same stories for a before/after comparison.

    python validation/ebike_type_v2/evaluate.py
"""
from __future__ import annotations

import csv
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
from neissai.ebike_type import ebike_type as v2  # noqa: E402

spec = importlib.util.spec_from_file_location("v14", HERE / "ebike_type_v1_4.py")
m14 = importlib.util.module_from_spec(spec); spec.loader.exec_module(m14)
v14 = m14.ebike_type

LABELS = ("regular e-bike", "likely e-moto", "unclear")
rows = list(csv.DictReader(open(HERE / "ebike_type_TEST2_240.csv", newline="")))
pop = json.loads((HERE / "population.json").read_text())["by_group"]
n_g = Counter(r["stratum"] for r in rows)
w = np.array([pop[r["stratum"]] / n_g[r["stratum"]] for r in rows])
ref = [r["reference_label"] for r in rows]
groups = sorted(n_g)
gidx = {g: np.array([i for i, r in enumerate(rows) if r["stratum"] == g]) for g in groups}


def stats(rule):
    pred = [rule(r["narrative"]) for r in rows]
    ok = np.array([p == y for p, y in zip(pred, ref)], dtype=float)
    acc = float((w * ok).sum() / w.sum())
    rng = np.random.RandomState(2026)
    boots = []
    for _ in range(2000):
        idx = np.concatenate([rng.choice(gidx[g], size=len(gidx[g]), replace=True) for g in groups])
        boots.append((w[idx] * ok[idx]).sum() / w[idx].sum())
    lo, hi = np.percentile(boots, [2.5, 97.5])
    per = {}
    for c in LABELS:
        tp = sum(wi for wi, p, y in zip(w, pred, ref) if p == c and y == c)
        pp = sum(wi for wi, p in zip(w, pred) if p == c)
        ap = sum(wi for wi, y in zip(w, ref) if y == c)
        per[c] = {"precision": tp / pp if pp else float("nan"), "recall": tp / ap if ap else float("nan"),
                  "share_rule": pp / w.sum(), "share_reviewers": ap / w.sum()}
    misses = [(y, p, r["narrative"]) for p, y, r in zip(pred, ref, rows) if p != y]
    return {"weighted": acc, "ci": (float(lo), float(hi)), "raw": int(ok.sum()), "n": len(rows), "per": per, "misses": misses}


out = {"v2 (new)": stats(v2), "v1.4 (old)": stats(v14)}
agree = sum(r["reviewer1"] == r["reviewer2"] for r in rows)
lines = ["# Fresh test results: e-bike vs e-moto rule (scored once, after locking)", "",
         f"240 new stories (2019-2025), none used before; labelled blind by two AI reviewers working only from "
         f"DEFINITIONS.md (agreed on {agree}/240; a third settled the rest). Weighted to all "
         f"{sum(pop.values()):,} e-bike stories.", "",
         "| Rule | Right (weighted) | 95% CI | Right (raw) |", "| --- | --- | --- | --- |"]
for k, s in out.items():
    lines.append(f"| {k} | {s['weighted']:.1%} | {s['ci'][0]:.1%}-{s['ci'][1]:.1%} | {s['raw']}/{s['n']} ({s['raw'] / s['n']:.1%}) |")
s = out["v2 (new)"]
lines += ["", "v2 by group (weighted):", "", "| Group | Precision | Recall | Share by rule | Share by reviewers |", "| --- | --- | --- | --- | --- |"]
for c, d in s["per"].items():
    lines.append(f"| {c} | {d['precision']:.1%} | {d['recall']:.1%} | {d['share_rule']:.1%} | {d['share_reviewers']:.1%} |")
lines += ["", f"v2 misses ({len(s['misses'])}):", ""] + [f"- reviewers: {y}; rule: {p} | {t[:200]}" for y, p, t in s["misses"]]
(HERE / "RESULTS.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
