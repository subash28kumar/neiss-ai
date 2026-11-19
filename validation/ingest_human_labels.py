"""Turn reviewers' Set C labels into NEISS-AI's human memory, with guardrails.

    python validation/ingest_human_labels.py [CSV ...]

With no arguments it reads every CSV in validation/learning/submissions/. It applies the
guardrails in neissai.learn (trusted reviewers only, spot checks, at least two people agreeing,
locked test stories never learned) and writes

  validation/learning/human_memory.json    what NEISS-AI will learn (only after check_learning passes)
  validation/learning/ingest_report.md     who was used, who was left out and why (no names)

Reviewer CSVs and trusted_labellers.csv hold names, so they stay out of git (.gitignore).

Deterministic: the same files always give the same memory.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
from neissai import learn as L  # noqa: E402

LD = HERE / "learning"


def main(argv):
    files = [Path(a) for a in argv] or sorted((LD / "submissions").glob("*.csv"))
    rows = L.read_label_csvs(files)
    items = {r["id"]: r["text"] for r in csv.DictReader(open(LD / "set_c_items.csv", newline=""))}
    spot = {r["id"]: {q: r[q] for q in L.QUESTIONS} for r in csv.DictReader(open(LD / "set_c_spotcheck.csv", newline=""))}
    trusted = L.read_trusted(LD / "trusted_labellers.csv")
    memory, rep = L.build_memory(rows, items, spot, trusted, L.locked_ids())
    out = {"version": 1, "rules": {"min_agree": L.MIN_AGREE, "min_share": L.MIN_SHARE, "spot_min": L.SPOT_MIN,
                                   "spot_pass": L.SPOT_PASS, "closest_match": L.CLOSE},
           "n_files": len(files), "entries": [memory[k] for k in sorted(memory)]}
    (LD / "human_memory.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    lines = ["# Human labels: ingest report", "", f"Files read: {len(files)}; rows: {len(rows)}", "",
             "| Reviewer | Rows | Trusted | Spot checks right | Used? |", "| --- | --- | --- | --- | --- |"]
    for n, (who, i) in enumerate(rep["labellers"].items(), 1):  # names stay private: "Reviewer 1", ...
        sc = f"{i['spot_right']} of {i['spot_checks']}" if i["spot_checks"] else "none answered"
        lines.append(f"| Reviewer {n} | {i['rows']} | {'yes' if i['trusted'] else 'no'} | {sc} | {i['reason']} |")
    lines += ["", f"Learned answers: {rep['learned']} (on {rep['stories']} stories)", ""]
    lines += [f"- Skipped, {k}: {v}" for k, v in rep["skipped"].items()]
    (LD / "ingest_report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main(sys.argv[1:])
