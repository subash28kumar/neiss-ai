"""Train the e-bike vs moped classifier with a proper 70/15/15 train / validation / test split.

    python scripts/train_classifier_split.py --data-dir data --years 2024-2025

Labels: CPSC product codes 5045 (e-bike) vs 5046 (other power-assisted cycles); records with
both codes are dropped. Deterministic: each record goes to a split by the SHA-1 of its CPSC case
number (no random seed), so the split never changes.

1. Train on 70%, pick the regularisation strength C by validation AUC (15%).
2. Retrain on train + validation (85%) with that C.
3. Score ONCE on the locked test (15%): AUC, accuracy, sensitivity, specificity, with bootstrap
   95% CIs (fixed seed). Writes the model, the split list and validation/classifier_v2/RESULTS.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from neissai.classifier import EbikeMopedClassifier
from neissai.io import read_neiss

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "validation" / "classifier_v2"
GRID = (0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0)


def split_of(case: str) -> str:
    h = int(hashlib.sha1(("neissai-clf-v2|" + str(case).strip()).encode()).hexdigest(), 16) % 100
    return "train" if h < 70 else "validation" if h < 85 else "test"


def auc(y, p):
    y, p = np.asarray(y), np.asarray(p)
    order = np.argsort(p, kind="mergesort")
    ranks = np.empty(len(p)); ranks[order] = np.arange(1, len(p) + 1)
    for v in np.unique(p):                      # average ranks for ties
        m = p == v
        ranks[m] = ranks[m].mean()
    n1 = y.sum(); n0 = len(y) - n1
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def metrics(y, p):
    y, p = np.asarray(y), np.asarray(p)
    pred = (p >= 0.5).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum()); tn = int(((pred == 0) & (y == 0)).sum())
    return {"auc": auc(y, p), "accuracy": float((pred == y).mean()), "sensitivity": tp / int(y.sum()),
            "specificity": tn / int((1 - y).sum()), "n": int(len(y)), "n_ebike": int(y.sum())}


def boot(y, p, seed=2026, reps=2000):
    y, p = np.asarray(y), np.asarray(p)
    rng = np.random.RandomState(seed)
    out = {k: [] for k in ("auc", "accuracy", "sensitivity", "specificity")}
    for _ in range(reps):
        i = rng.randint(0, len(y), len(y))
        if 0 < y[i].sum() < len(i):
            m = metrics(y[i], p[i])
            for k in out:
                out[k].append(m[k])
    return {k: (float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))) for k, v in out.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--years", default="2024-2025")
    ap.add_argument("--out", default="src/neissai/model/ebike_moped_v2.json")
    a = ap.parse_args()
    df = read_neiss(a.data_dir, a.years)
    codes = df[["Product_1", "Product_2", "Product_3"]].astype(str)
    eb, mo = codes.isin(["5045"]).any(axis=1), codes.isin(["5046"]).any(axis=1)
    d = df[eb ^ mo].copy()
    d["y"] = eb[d.index].astype(int)
    d["text"] = d["Narrative"].astype(str).str.upper()
    d["split"] = d["CPSC_Case_Number"].map(split_of)
    d = d.sort_values("CPSC_Case_Number", kind="mergesort")
    tr, va, te = (d[d.split == s] for s in ("train", "validation", "test"))

    tuning = []
    for C in GRID:
        m = EbikeMopedClassifier.fit(tr.text.tolist(), tr.y.tolist(), C=C, cv_folds=0)
        tuning.append((C, auc(va.y, m.predict_proba(va.text.tolist()))))
    best_C = sorted(tuning, key=lambda t: (-round(t[1], 6), t[0]))[0][0]

    final = EbikeMopedClassifier.fit(pd_list(tr, va, "text"), pd_list(tr, va, "y"), C=best_C, cv_folds=0)
    p_test = np.array(final.predict_proba(te.text.tolist()))
    res, ci = metrics(te.y, p_test), boot(te.y.to_numpy(), p_test)
    final.meta.update({"years": a.years, "split": "70/15/15 by SHA-1 of case number", "C": best_C,
                       "n_train": int(len(tr) + len(va)), "n_test": res["n"],
                       "test_auc": round(res["auc"], 4), "test_accuracy": round(res["accuracy"], 4)})
    final.meta.pop("cv_auc", None)
    final.to_json(a.out)

    OUT.mkdir(parents=True, exist_ok=True)
    d[["CPSC_Case_Number", "year", "y", "split"]].rename(columns={"y": "is_ebike_5045"}).to_csv(OUT / "split.csv", index=False)
    lines = ["# E-bike vs moped classifier: train / validation / test results (v2)", "",
             f"Data: NEISS {a.years}, records coded 5045 (e-bike) or 5046 (other power-assisted cycle), not both: "
             f"{len(d):,} stories ({int(d.y.sum()):,} e-bikes).", "",
             "| Split | Stories | Share | E-bikes |", "| --- | --- | --- | --- |"]
    for name, s in (("Train", tr), ("Validation", va), ("Test (locked)", te)):
        lines.append(f"| {name} | {len(s):,} | {len(s) / len(d):.0%} | {int(s.y.sum()):,} |")
    lines += ["", "Tuning on validation (AUC by regularisation strength C):", "",
              "| C | Validation AUC |", "| --- | --- |"] + [f"| {C} | {v:.4f} |" for C, v in tuning]
    lines += ["", f"Chosen C = {best_C}. Final model retrained on train + validation, then scored once on the test set.", "",
              "| Test result | Value | 95% CI |", "| --- | --- | --- |"]
    for k, lab in (("auc", "AUC"), ("accuracy", "Accuracy (cut-off 0.5)"), ("sensitivity", "Sensitivity (e-bikes found)"),
                   ("specificity", "Specificity (mopeds kept out)")):
        lines.append(f"| {lab} | {res[k]:.3f} | {ci[k][0]:.3f}-{ci[k][1]:.3f} |")
    (OUT / "RESULTS.md").write_text("\n".join(lines) + "\n")
    (OUT / "results.json").write_text(json.dumps({"tuning": tuning, "C": best_C, "test": res, "ci": ci}, indent=1) + "\n")
    print("\n".join(lines))


def pd_list(a, b, col):
    return a[col].tolist() + b[col].tolist()


if __name__ == "__main__":
    main()
