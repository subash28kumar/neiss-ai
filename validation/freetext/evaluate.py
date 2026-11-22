"""How well does text-only labelling (no product codes) agree with NEISS-AI's full labels?

Input: the site's own data (docs/data/records.json + stories.json): every NEISS 2019-2025 record
that NEISS-AI labels as one of 7 micromobility devices, with its story. Full labels use the
CPSC product codes AND the story; here the codes are hidden and only the story is used.
Two versions of each story: the full NEISS story, and a SHORT version (first 60 characters) as
a rough stand-in for a brief triage note. Results are weighted (national estimates) and raw.
Run: PYTHONPATH=src python3 validation/freetext/evaluate.py
"""
import json, collections, sys
from pathlib import Path
sys.path.insert(0, "src")
from neissai.freetext import label_notes
import pandas as pd

root = Path(__file__).resolve().parents[2]
r = json.load(open(root / "docs/data/records.json")); s = json.load(open(root / "docs/data/stories.json"))
df = pd.DataFrame({"full": [r["devices"][d] for d in r["d"]], "year": [r["years"][y] for y in r["y"]],
                   "w": r["w"], "text": s})
out = {}
for version, col in (("full story", "text"), ("short note (first 60 characters)", "short")):
    if col == "short":
        df["short"] = df["text"].str.slice(0, 60)
    lab = label_notes(df[[col]], col)
    df["tx"] = lab["device"].values
    res = {}
    for dev in r["devices"]:
        m = df["full"] == dev
        same = m & (df["tx"] == dev)
        res[dev] = {"records": int(m.sum()), "agree_raw": round(100 * same.sum() / m.sum(), 1),
                    "agree_weighted": round(100 * df.loc[same, "w"].sum() / df.loc[m, "w"].sum(), 1),
                    "text_only_said": dict(collections.Counter(df.loc[m & ~same, "tx"]).most_common(3))}
    allm = df["full"].isin(r["devices"])
    res["ALL 7 devices"] = {"records": int(allm.sum()),
                            "agree_raw": round(100 * (df["full"] == df["tx"]).mean(), 1),
                            "agree_weighted": round(100 * df.loc[df["full"] == df["tx"], "w"].sum() / df["w"].sum(), 1)}
    # national e-bike and e-scooter totals, 2025, both ways
    for dev in ("E-bike", "E-scooter"):
        y = df["year"] == 2025
        res[f"{dev} 2025 national estimate"] = {"full_labels": round(df.loc[y & (df["full"] == dev), "w"].sum()),
                                                 "text_only": round(df.loc[y & (df["tx"] == dev), "w"].sum())}
    out[version] = res
(root / "validation/freetext/results.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
