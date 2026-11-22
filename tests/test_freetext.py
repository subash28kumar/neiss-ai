"""Tests for labelling injury notes from any hospital data (text, optional ICD-10-CM codes)."""
import pandas as pd
import pytest

from neissai import freetext, label_note, label_notes
from neissai.cli import main


@pytest.mark.parametrize("text,device", [
    ("PT FELL OFF EBIKE HIT CURB", "E-bike"),
    ("23YOM RIDING AN ELECTRIC BICYCLE, HIT BY A CAR", "E-bike"),
    ("RIDING ELECTRIC SCOOTER STRUCK BY CAR", "E-scooter"),
    ("FELL OFF HIS KICK SCOOTER", "Kick scooter"),
    ("FELL OFF SCOOTER", "Scooter (type not stated)"),
    ("FELL FROM BICYCLE ONTO WRIST", "Bicycle"),
    ("SKATEBOARD FALL", "Skateboard"),
    ("RIDING HOVERBOARD AND FELL", "Hoverboard"),
    ("FELL OFF HIS SEGWAY", "Other standing micromobility"),
    ("RIDING MOPED FELL", "Moped / minibike"),
    ("MOBILITY SCOOTER TIPPED OVER", "Excluded"),
    ("FELL OFF EXERCISE BIKE", "Excluded"),
    ("CHEST PAIN AT HOME", "Other"),
    ("", "Other"),
])
def test_words_only(text, device):
    assert label_note(text)["device"] == device


def test_emoto_words_count_as_ebike_and_are_flagged():
    r = label_note("RIDING BIKE GOING 35 MPH ON HIS SURRON")
    assert r["device"] == "E-bike" and r["ebike_type"] == "likely e-moto" and r["rider_mph"] == 35


def test_circumstances_read_from_any_text():
    r = label_note("RIDING E-SCOOTER, HIT BY A CAR, NO HELMET")
    assert r["helmet"] == "no" and r["motor_vehicle"] is True


@pytest.mark.parametrize("code,device,role", [
    ("V00.841A", "E-scooter", "rider"),          # fall from standing e-scooter
    ("V00842A", "E-scooter", "rider"),
    ("V01.131A", "E-scooter", "rider"),          # on standing e-scooter, hit by pedal cycle
    ("V00.031A", "E-scooter", "struck by rider"),  # on foot, hit by e-scooter rider
    ("V00.848A", "Other standing micromobility", "rider"),
    ("V00.141A", "Kick scooter", "rider"),
    ("V00.131A", "Skateboard", "rider"),
    ("V28.01XA", "E-bike", "rider"),             # electric (assisted) bicycle driver
    ("V20.91XA", "E-bike", "rider"),
    ("V29.811A", "E-bike", "rider"),
    ("V28.09XA", "Moped / minibike", "rider"),   # other motorcycle
    ("V18.0XXA", "Bicycle", "rider"),
    ("V00.831A", "Excluded", "rider"),           # motorized mobility scooter
])
def test_icd10cm_codes(code, device, role):
    assert freetext.device_from_codes(code) == (device, role)


def test_non_micromobility_codes_ignored():
    assert freetext.device_from_codes("S52.501A; W19.XXXA") == (None, None)


def test_code_settles_unstated_scooter():
    assert label_note("FELL OFF SCOOTER", "V00.841A")["device"] == "E-scooter"
    assert label_note("FELL OFF SCOOTER", "V00.141A")["device"] == "Kick scooter"


def test_hoverboard_words_refine_other_standing_code():
    r = label_note("HOVERBOARD FALL", "V00.848A")
    assert r["device"] == "Hoverboard" and r["device_how"] == "code+words"


def test_ebike_words_override_bicycle_or_motorcycle_code():
    # The same rule NEISS-AI uses: e-bike words inside a bicycle code mean an e-bike.
    r = label_note("RIDING HIS E-BIKE AND FELL", "V18.0XXA")
    assert r["device"] == "E-bike" and r["device_how"] == "code+words"


def test_code_alone_when_text_is_empty():
    r = label_note("", "V28.41XA")
    assert r["device"] == "E-bike" and r["device_how"] == "code"


def test_custom_code_map_for_other_countries():
    cmap = [("V10", "Bicycle", "rider"), ("V99X", "E-scooter", "rider")]
    assert freetext.device_from_codes("V99X1", code_map=cmap) == ("E-scooter", "rider")
    assert freetext.device_from_codes("V00.841A", code_map=cmap) == (None, None)


def test_label_notes_table_keeps_rows_and_columns():
    df = pd.DataFrame({"visit_id": [1, 2, 3], "note": ["FELL OFF EBIKE", "FELL OFF SCOOTER", "CHEST PAIN"],
                       "ecode": ["", "V00.841A", None]})
    out = label_notes(df, "note", code_cols="ecode")
    assert list(out["visit_id"]) == [1, 2, 3]
    assert list(out["device"]) == ["E-bike", "E-scooter", "Other"]
    with pytest.raises(KeyError):
        label_notes(df, "missing_column")


def test_cli_label_notes(tmp_path, capsys):
    src = tmp_path / "notes.csv"
    pd.DataFrame({"note": ["FELL OFF EBIKE", "RIDING BICYCLE FELL", "FELL OFF SCOOTER"],
                  "ecode": ["", "", "V00.841A"]}).to_csv(src, index=False)
    dest = tmp_path / "out.csv"
    assert main(["label-notes", str(src), "--text-col", "note", "--code-cols", "ecode", "--out", str(dest)]) == 0
    out = pd.read_csv(dest)
    assert list(out["device"]) == ["E-bike", "Bicycle", "E-scooter"]
    assert "never leaves this computer" in capsys.readouterr().out
