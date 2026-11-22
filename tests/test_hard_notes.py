"""The hard-notes test must pick exactly the notes the live pipeline sends to the model."""
import importlib.util
from pathlib import Path

import pandas as pd

import neissai

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("hard", ROOT / "validation" / "classifier_v2" / "hard_notes.py")
hard = importlib.util.module_from_spec(spec); spec.loader.exec_module(hard)

NOTES = ["PT FELL OFF E-BIKE", "PT RIDING BIKE AT 20MPH FELL", "FELL FROM BICYCLE WITH BATTERY",
         "PT FELL OFF MOPED", "PT ON SCOOTER FELL", "FELL OFF ELECTRIC BICYCLE", "DIRT BIKE CRASH",
         "RIDING 2 WHEELED VEHICLE CRASHED", "FELL OFF SCOOTER AND BIKE", "MOTORCYCLE CRASH"]


def test_hard_rule_matches_pipeline():
    df = pd.DataFrame({"Narrative": NOTES, "Product_1": ["3215"] * len(NOTES), "Product_2": "0", "Product_3": "0",
                       "Weight": 1.0, "PSU": 1, "Stratum": "V", "CPSC_Case_Number": range(len(NOTES))})
    lab = neissai.label_devices(df)
    sent_to_model = (lab["label_source"] == "classifier").tolist()
    assert hard.is_hard(pd.Series(NOTES)).tolist() == sent_to_model
    assert any(sent_to_model) and not all(sent_to_model)
