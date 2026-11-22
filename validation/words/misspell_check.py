"""Check the misspelled e-bike words against the hospital's own codes (2024-2025).

    python validation/words/misspell_check.py --data-dir data

For every 2024-2025 note coded 5045 (e-bike) or 5046 (moped), not both, whose story matches
neissai.devices.E_MISSPELLED: how many were coded e-bike. Also: how many bicycle-coded notes, and
how many 2019-2023 code-3215 notes, the words touch. Writes validation/words/MISSPELL_CHECK.md.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from neissai.devices import BIKE_CODES, E_MISSPELLED, _kw
from neissai.io import read_neiss

OUT = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    a = ap.parse_args()
    df = read_neiss(a.data_dir, "2019-2025")
    text = df["Narrative"].astype(str).str.upper()
    hit = _kw(text, E_MISSPELLED)
    codes = df[["Product_1", "Product_2", "Product_3"]].astype(str)
    has = lambda *c: codes.isin(list(c)).any(axis=1)
    new = df["year"] >= 2024
    eb, mo = has("5045"), has("5046")
    rows = [("2024-25, coded e-bike (5045)", int((hit & new & eb & ~mo).sum())),
            ("2024-25, coded moped (5046)", int((hit & new & mo & ~eb).sum())),
            ("2024-25, coded bicycle (now counted as e-bike)", int((hit & new & has(*BIKE_CODES) & ~eb & ~mo).sum())),
            ("2019-23, coded bicycle (now counted as e-bike)", int((hit & ~new & has(*BIKE_CODES) & ~has("3215")).sum())),
            ("2019-23, coded 3215 (now decided by words, not the model)", int((hit & ~new & has("3215")).sum()))]
    e, m = rows[0][1], rows[1][1]
    lines = ["# Misspelled e-bike words checked against hospital codes", "",
             "Sample records whose story matches `E_MISSPELLED` in `src/neissai/devices.py`.", "",
             "| Group | Records |", "| --- | --- |"] + [f"| {g} | {n} |" for g, n in rows]
    lines += ["", f"Of the 2024-2025 notes with a separate e-bike or moped code, {e} of {e + m} "
              f"({100 * e / max(e + m, 1):.1f}%) were coded e-bike."]
    (OUT / "MISSPELL_CHECK.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
