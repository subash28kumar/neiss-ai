"""Test the e-bike vs moped model on the HARD notes: the kind it decides before 2024.

    python validation/classifier_v2/hard_notes.py --data-dir data

Before 2024, e-bikes and mopeds shared CPSC code 3215, and NEISS-AI sends a record to the model only
when its note names neither (no e-bike words and no moped words). Those older notes have no answer
key. The closest fair test: 2024-2025 notes coded 5045 (e-bike) or 5046 (moped), where the hospital's
code IS the answer, that also name neither device, and that are in the model's locked TEST split
(never used for training or tuning). Same split rule as scripts/train_classifier_split.py.
Writes validation/classifier_v2/HARD_NOTES.md and hard_notes.json.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np

from neissai.classifier import EbikeMopedClassifier
from neissai.devices import E_WORDS, MOPED_WORDS, _kw
from neissai.io import read_neiss

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "validation" / "classifier_v2"
spec = importlib.util.spec_from_file_location("tcs", ROOT / "scripts" / "train_classifier_split.py")
tcs = importlib.util.module_from_spec(spec); spec.loader.exec_module(tcs)


def is_hard(text):
    """True for the notes NEISS-AI would hand to the model under the old shared code 3215:
    no e-bike words, no moped words, and not a scooter-only story (those are ruled out first)."""
    scooter_only = _kw(text, r"SCOOTER") & ~_kw(text, r"BIKE|BICYCL|CYCLE")
    return ~_kw(text, E_WORDS) & ~_kw(text, MOPED_WORDS) & ~scooter_only


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    a = ap.parse_args()
    df = read_neiss(a.data_dir, "2024-2025")
    codes = df[["Product_1", "Product_2", "Product_3"]].astype(str)
    eb, mo = codes.isin(["5045"]).any(axis=1), codes.isin(["5046"]).any(axis=1)
    d = df[eb ^ mo].copy()
    d["y"] = eb[d.index].astype(int)
    d["text"] = d["Narrative"].astype(str).str.upper()
    d["split"] = d["CPSC_Case_Number"].map(tcs.split_of)
    d["hard"] = is_hard(d.text)
    te = d[d.split == "test"]
    clf = EbikeMopedClassifier.load_default()
    out = {}
    for name, sub in (("all test notes", te), ("HARD test notes (no e-bike or moped words)", te[te.hard]),
                      ("easy test notes (name the device)", te[~te.hard])):
        p = np.array(clf.predict_proba(sub.text.tolist()))
        m = tcs.metrics(sub.y, p)
        ci = tcs.boot(sub.y.to_numpy(), p) if 0 < m["n_ebike"] < m["n"] else {}
        out[name] = {"metrics": m, "ci": ci}
    hard_all = d[d.hard]
    out["share of all 2024-2025 5045/5046 notes that are hard"] = round(float(d.hard.mean()), 4)
    out["hard notes in all splits"] = int(len(hard_all))
    out["hard test examples"] = [{"code": "5045 e-bike" if r.y else "5046 moped", "p_ebike": round(float(p), 3),
                                  "text": r.text[:160]}
                                 for (r, p) in zip(te[te.hard].head(25).itertuples(),
                                                   clf.predict_proba(te[te.hard].head(25).text.tolist()))]
    (OUT / "hard_notes.json").write_text(json.dumps(out, indent=1) + "\n")
    f = lambda x: f"{100 * x:.1f}%"
    lines = ["# E-bike vs moped model on HARD notes (the kind it decides before 2024)", "",
             "Notes coded 5045 (e-bike) or 5046 (moped) in 2024-2025, in the model's locked test split, "
             "that name neither device. The hospital's code is the answer key. Same model the site uses.", "",
             "| Notes | Number (e-bikes) | Accuracy | E-bikes found | Mopeds kept out | AUC |", "| --- | --- | --- | --- | --- | --- |"]
    for name in ("all test notes", "HARD test notes (no e-bike or moped words)", "easy test notes (name the device)"):
        m, ci = out[name]["metrics"], out[name]["ci"]
        c = (lambda k: f" [{f(ci[k][0])}-{f(ci[k][1])}]" if ci else "")
        lines.append(f"| {name} | {m['n']} ({m['n_ebike']}) | {f(m['accuracy'])}{c('accuracy')} | {f(m['sensitivity'])}{c('sensitivity')} | "
                     f"{f(m['specificity'])}{c('specificity')} | {m['auc']:.3f} |")
    lines += ["", f"Hard notes are {f(out['share of all 2024-2025 5045/5046 notes that are hard'])} of all 2024-2025 5045/5046 notes.", "",
              "Limit: these are 2024-2025 notes. Notes written before 2024 may differ (for example, staff may "
              "have written 'moped' or 'e-bike' less often when one code covered both). This is the closest test "
              "possible without a hand-checked answer key for older notes.", "",
              "Run: `python validation/classifier_v2/hard_notes.py --data-dir data` (needs CPSC's 2024-2025 files)."]
    (OUT / "HARD_NOTES.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
