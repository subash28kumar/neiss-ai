"""Build docs/data/label_sets.json for the blind labelling page (docs/label.html).

Sets A and B are locked accuracy tests (never learned from). Set C ("Help train") is built by
scripts/build_train_set.py from the hardest e-bike stories; trusted answers to it teach NEISS-AI.

Only the case number and the story are written. The reference answers and NEISS-AI's own
answers are NOT included, so volunteers label blind. Their CSV is scored later with
validation/score_human_labels.py.

    python scripts/build_label_sets.py
"""
import csv
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_train_set import train_set  # noqa: E402
VAL = ROOT / "validation"


def items(name, id_col, seed):
    with open(VAL / name, newline="") as f:
        rows = [{"id": r[id_col], "text": " ".join(r["narrative"].upper().split())} for r in csv.DictReader(f)]
    random.Random(seed).shuffle(rows)  # fixed order for everyone; mixes the sampling groups
    return rows


sets = [
    {"id": "A", "file": "injurycoder_test_300.csv", "title": "Set A: motor vehicle and helmet (300 stories)",
     "questions": ["mv", "helmet"], "items": items("injurycoder_test_300.csv", "cpsc_case_number", 12)},
    {"id": "B", "file": "ebike_type_TEST_240.csv", "title": "Set B: regular e-bike or e-moto (240 stories)",
     "questions": ["etype"], "items": items("ebike_type_TEST_240.csv", "CPSC_Case_Number", 13)},
]
for s in sets:
    s["note"] = "Blind accuracy check: these are locked test stories that NEISS-AI never learns from."
c = train_set()
c["note"] = ("Help NEISS-AI learn: the hardest e-bike stories. Your answers teach the tool only when at least two "
             "approved reviewers agree. A few stories with known answers are mixed in as quality checks.")
sets.append({k: c[k] for k in ("id", "title", "questions", "learn", "note", "items")})
out = ROOT / "docs" / "data" / "label_sets.json"
out.write_text(json.dumps({"sets": sets}, separators=(",", ":")))
print("wrote", out, [len(s["items"]) for s in sets])
