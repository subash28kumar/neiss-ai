"""Gate for a new human memory: it may go live only if accuracy on the locked tests does not drop.

    python validation/check_learning.py            # exit code 1 if any accuracy drops

Compares NEISS-AI's rules alone with rules + human memory (validation/learning/human_memory.json)
on the locked test sets: 240 e-bike/e-moto stories and 300 motor vehicle/helmet stories. These
stories are never learned from, so memory can only reach them through a closest match.
Writes validation/learning/check_report.md. Deterministic.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
from neissai import learn as L  # noqa: E402
from neissai.circumstances import helmet, motor_vehicle  # noqa: E402
from neissai.ebike_type import ebike_type  # noqa: E402

NORM = {"true": "yes", "false": "no", "1": "yes", "0": "no"}


def n(v):
    v = str(v).strip().lower()
    return NORM.get(v, v)


def score(rows, key, rule, mem, q):
    texts = [r["narrative"] for r in rows]
    hits = mem.lookup_many(texts, q) if len(mem) else [None] * len(rows)
    base = sum(rule(t) == n(r[key]) for t, r in zip(texts, rows))
    new = sum((h["label"] if h else rule(t)) == n(r[key]) for t, r, h in zip(texts, rows, hits))
    changed = sum(1 for h in hits if h)
    return base, new, changed, len(rows)


def main():
    mem = L.HumanMemory.load()
    e = list(csv.DictReader(open(HERE / "ebike_type_TEST_240.csv", newline="")))
    a = list(csv.DictReader(open(HERE / "injurycoder_test_300.csv", newline="")))
    res = {
        "E-bike vs e-moto (240)": score(e, "reference_label", ebike_type, mem, "etype"),
        "Motor vehicle (300)": score(a, "motor_vehicle", lambda t: "yes" if motor_vehicle(t) else "no", mem, "mv"),
        "Helmet (300)": score(a, "helmet", helmet, mem, "helmet"),
    }
    ok = all(new >= base for base, new, _, _ in res.values())
    lines = ["# Learning check (locked tests)", "", f"Human memory: {len(mem)} stories", "",
             "| Test | Rules alone | Rules + human memory | Answers changed by memory |", "| --- | --- | --- | --- |"]
    for name, (base, new, ch, tot) in res.items():
        lines.append(f"| {name} | {base}/{tot} ({base / tot:.1%}) | {new}/{tot} ({new / tot:.1%}) | {ch} |")
    lines += ["", "Counts are unweighted. The website's e-bike vs e-moto figure (98.4%) is weighted by how common "
              "each kind of story is, because the test set over-samples hard stories.",
              "", "PASS: no accuracy drop. The memory may go live." if ok else
              "FAIL: accuracy dropped. Do not publish this memory; review the closest matches."]
    (HERE / "learning" / "check_report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
