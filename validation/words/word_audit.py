"""Which words come right before BIKE / BICYCLE, and how hospitals coded those notes.

    python validation/words/word_audit.py --data-dir data

Finds misspellings and other words for e-bikes that the word rules miss. For 2024-2025 the hospital code
(5045 e-bike, 5046 moped, bicycle codes) is the answer key; for 2019-2023 it shows how many code-3215
notes each word would affect. Writes validation/words/WORD_AUDIT.md and word_audit.csv.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from neissai.devices import BIKE_CODES, E_WORDS, MOPED_WORDS, _kw
from neissai.io import read_neiss

OUT = Path(__file__).resolve().parent
PREV = r"\b([A-Z][A-Z\-]*-? ?)(?=BIKES?\b|BICYCLES?\b)"


def group(row_codes, year):
    c = set(row_codes)
    if year >= 2024 and "5045" in c and "5046" not in c:
        return "2024-25 coded e-bike (5045)"
    if year >= 2024 and "5046" in c and "5045" not in c:
        return "2024-25 coded moped (5046)"
    if c & set(BIKE_CODES) and not c & {"5045", "5046", "3215"}:
        return f"{'2024-25' if year >= 2024 else '2019-23'} coded bicycle"
    if year < 2024 and "3215" in c:
        return "2019-23 coded 3215 (shared)"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    a = ap.parse_args()
    df = read_neiss(a.data_dir, "2019-2025")
    df["text"] = df["Narrative"].astype(str).str.upper()
    codes = df[["Product_1", "Product_2", "Product_3"]].astype(str).values.tolist()
    df["group"] = [group(c, y) for c, y in zip(codes, df["year"])]
    d = df[df.group.notna()].copy()
    d["e_words"] = _kw(d.text, E_WORDS)
    d["moped_words"] = _kw(d.text, MOPED_WORDS)
    d = d[~d.e_words & ~d.moped_words]                 # only notes the rules do NOT already decide
    d["prev"] = d.text.str.extract(PREV, expand=False).str.strip().str.rstrip("-").str.strip()
    t = d.dropna(subset=["prev"]).groupby(["prev", "group"]).size().unstack(fill_value=0)
    t["total"] = t.sum(axis=1)
    t = t.sort_values("total", ascending=False)
    t.to_csv(OUT / "word_audit.csv")
    top = t.head(150)
    lines = ["# Words right before BIKE / BICYCLE in notes the word rules do not decide", "",
             "Notes with an existing e-bike or moped word are left out. Counts are sample records (not weighted).", "",
             "| Word | " + " | ".join(top.columns) + " |", "| --- |" + " --- |" * len(top.columns)]
    for w, r in top.iterrows():
        lines.append(f"| {w} | " + " | ".join(str(int(v)) for v in r) + " |")
    (OUT / "WORD_AUDIT.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:60]))


if __name__ == "__main__":
    main()
