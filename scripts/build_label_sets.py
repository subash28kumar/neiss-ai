"""Build docs/data/label_sets.json for the blind labelling page (docs/label.html).

Only the case number and the story are written. The reference answers and NEISS-AI's own
answers are NOT included, so volunteers label blind. Their CSV is scored later with
validation/score_human_labels.py.

    python scripts/build_label_sets.py
"""
import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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
out = ROOT / "docs" / "data" / "label_sets.json"
out.write_text(json.dumps({"sets": sets}, separators=(",", ":")))
print("wrote", out, [len(s["items"]) for s in sets])
