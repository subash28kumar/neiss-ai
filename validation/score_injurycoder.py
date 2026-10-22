"""Score the InjuryCoder rules on the held-out test set.

    python validation/score_injurycoder.py
"""
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from neissai.circumstances import helmet, motor_vehicle  # noqa: E402

t = pd.read_csv(ROOT / "validation" / "injurycoder_test_300.csv")
mv = t["narrative"].map(motor_vehicle).map({True: "Yes", False: "No"})
h = t["narrative"].map(helmet).map({"yes": "Yes", "no": "No", "not mentioned": "Not mentioned"})
tp = ((mv == "Yes") & (t["motor_vehicle"] == "Yes")).sum()
print(f"Motor vehicle: {(mv == t['motor_vehicle']).sum()}/{len(t)} correct; "
      f"found {tp}/{(t['motor_vehicle'] == 'Yes').sum()} real cases; {tp}/{(mv == 'Yes').sum()} flags correct")
print(f"Helmet: {(h == t['helmet']).sum()}/{len(t)} correct")
