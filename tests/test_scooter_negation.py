"""Scooters the story says are NOT powered must not be counted as e-scooters (independent review, Nov 2026)."""
import pandas as pd

from neissai.devices import label_devices
from neissai.freetext import label_note


def _lab(rows):
    df = pd.DataFrame({"Product_1": [c for c, _ in rows], "Product_2": "0", "Product_3": "0",
                       "Narrative": [n for _, n in rows]})
    return list(label_devices(df)["device"])


def test_negated_scooter_words_are_kick_scooters():
    rows = [("5024", "FELL OFF AN UNPOWERED SCOOTER"),
            ("5024", "10YOM FELL FROM NON-MOTORIZED SCOOTER"),
            ("5024", "FELL FROM NONMOTORIZED SCOOTER"),
            ("1329", "6YOF RIDING HER NONELECTRIC SCOOTER"),
            ("5023", "UN-POWERED SCOOTER FALL"),
            ("5024", "FELL OFF HIS SCOOTER, NOT AN ELECTRIC SCOOTER"),
            ("5022", "PT FELL OFF UNPOWERED SCOOTER")]
    assert _lab(rows) == ["Kick scooter"] * len(rows)


def test_real_e_scooters_unchanged():
    rows = [("5022", "FELL OFF ELECTRIC SCOOTER"),
            ("5024", "FELL OFF E-SCOOTER"),
            ("5022", "RIDING SCOOTER FELL"),
            ("5023", "MOTORIZED SCOOTER CRASH"),
            ("5024", "RIDING A LIME SCOOTER")]
    assert _lab(rows) == ["E-scooter"] * len(rows)


def test_own_notes_negated_scooters():
    assert label_note("FELL OFF AN UNPOWERED SCOOTER")["device"] == "Kick scooter"
    assert label_note("NON-MOTORIZED SCOOTER FALL, WRIST FX")["device"] == "Kick scooter"
    assert label_note("FELL OFF ELECTRIC SCOOTER")["device"] == "E-scooter"


def test_moped_code_scooter_stories_are_not_ebikes():
    rows = [("3215", "27-YOM RIDING A SCOOTER AT 20 MPH, FELL OFF SCOOTER"),
            ("3215", "72YM RIDING A MOTORIZED ELECTRIC SCOOTER & FELL"),
            ("3215", "45 YOM RIDING SCOOTER TO WORK, GOT HIT BY A CAR"),
            ("3215", "FELL OFF NON-ELECTRIC SCOOTER"),
            ("3215", "FELL OFF ELECTRIC BIKE")]
    assert _lab(rows) == ["Moped / minibike", "E-scooter", "Moped / minibike", "Moped / minibike", "E-bike"]
