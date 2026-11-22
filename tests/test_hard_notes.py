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


def test_misspelled_ebike_words():
    df = pd.DataFrame({"Narrative": ["PT FELL OFF ELETRIC BIKE", "RIDING ELECTRONIC BICYCLE, FELL", "FELL OFF E- BIKE",
                                     "PT FELL OFF MOTORIZED BIKE", "ELECTRICAL CORD CAUGHT IN BIKE"],
                       "Product_1": ["3215", "3215", "5040", "3215", "5040"], "Product_2": "0", "Product_3": "0",
                       "Weight": 1.0, "PSU": 1, "Stratum": "V", "CPSC_Case_Number": range(5)})
    lab = neissai.label_devices(df)
    assert lab.device.tolist()[:3] == ["E-bike"] * 3
    assert lab.label_source.tolist()[3] == "classifier"      # "motorized" stays with the model
    assert lab.device.tolist()[4] == "Bicycle"


def test_stationary_object_is_not_an_exercise_bike():
    df = pd.DataFrame({"Narrative": ["RIDING BIKE, CRASHED. DX: PEDAL CYCLIST COLLIDING WITH STATIONARY OBJECT",
                                     "FELL OFF STATIONARY BIKE AT GYM", "RIDING HIS ELECTIC BIKE, HIT FENCE. DX: COLLIDING WITH STATIONARY OBJECT",
                                     "INJURED ON EXERCISE BIKE AT HOME"],
                       "Product_1": ["5040", "5040", "3215", "5040"], "Product_2": "0", "Product_3": "0",
                       "Weight": 1.0, "PSU": 1, "Stratum": "V", "CPSC_Case_Number": range(4)})
    assert neissai.label_devices(df).device.tolist() == ["Bicycle", "Excluded", "E-bike", "Excluded"]
