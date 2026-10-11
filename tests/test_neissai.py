import numpy as np
import pandas as pd

import neissai
from neissai.io import parse_years, standardize


def _sample():
    rows = [
        # code, narrative, stratum, psu, weight, age, disposition
        ("5040", "14YOM FELL OFF HIS BICYCLE", "S", "1", 50.0, "14", "1"),
        ("5040", "30YOF RIDING THE BIKE AND FELL", "S", "2", 50.0, "30", "1"),
        ("5040", "40YOM FELL OFF ELECTRIC BIKE", "S", "1", 50.0, "40", "4"),
        ("5045", "16YOM FELL OFF EBIKE", "V", "3", 20.0, "16", "4"),
        ("3215", "25YOM CRASHED HIS MOPED", "V", "4", 20.0, "25", "1"),
        ("3215", "13YOM FELL OFF A POWER ASSISTED CYCLE GOING FAST PEDALING UPHILL", "V", "3", 20.0, "13", "1"),
        ("5022", "9YOF FELL OFF ELECTRIC SCOOTER", "M", "5", 80.0, "9", "1"),
        ("5022", "70YOM FELL FROM MOBILITY SCOOTER", "M", "6", 80.0, "70", "1"),
        ("1842", "50YOF ON EXERCISE BIKE STRAINED BACK", "M", "5", 80.0, "50", "1"),
        ("0000", "45YOM FELL OFF LADDER", "M", "6", 80.0, "45", "1"),
    ]
    df = pd.DataFrame(rows, columns=["Product_1", "Narrative_1", "Stratum", "PSU", "Weight", "Age", "Disposition"])
    df["Product_2"] = "0"
    df["Product_3"] = "0"
    df["Body_Part"] = "75"
    df["Alcohol"] = "0"
    df["Treatment_Date"] = "06/01/2024"
    return standardize(df, 2024)


def test_parse_years():
    assert parse_years("2019-2021,2025") == [2019, 2020, 2021, 2025]
    assert parse_years(2024) == [2024]


def test_labels_rules():
    lab = neissai.label_devices(_sample())
    dev = lab["device"].tolist()
    assert dev[0] == "Bicycle"
    assert dev[1] == "Bicycle"          # "the bike" must not match "e bike"
    assert dev[2] == "E-bike"           # narrative overrides bicycle code
    assert dev[3] == "E-bike"           # code 5045
    assert dev[4] == "Moped / minibike"
    assert lab["label_source"].iloc[5] == "classifier"
    assert dev[6] == "E-scooter"
    assert dev[7] == "Excluded"         # mobility scooter
    assert dev[9] == "Other"


def test_classifier_loads_and_separates():
    clf = neissai.EbikeMopedClassifier.load_default()
    p = clf.predict_proba(["16YOM FELL OFF ELECTRIC BIKE PEDAL ASSIST", "35YOM GAS MOPED CRASHED ON HIGHWAY"])
    assert clf.meta["cv_auc"] > 0.98
    assert p[0] > 0.5 > p[1]


def test_estimates_match_weights():
    lab = neissai.add_outcomes(neissai.label_devices(_sample()))
    est = neissai.total(lab, lab["device"] == "Bicycle")
    assert est["estimate"] == 100.0
    assert est["records"] == 2
    assert est["unstable"]                       # fewer than 20 records
    tab = neissai.national_estimates(lab, by=["device"], where=lab["device"].isin(neissai.DEVICES))
    assert set(tab["device"]) >= {"Bicycle", "E-bike", "E-scooter"}
    sh = neissai.proportion(lab, lab["hospitalized"] == 1, lab["device"] == "E-bike")
    assert 0 <= sh["share"] <= 1


def test_infant_age_conversion():
    df = _sample()
    raw = df.copy()
    raw.loc[0, "Age"] = 206.0
    out = standardize(raw.rename(columns={"Narrative": "Narrative_1"}), 2024)
    assert np.isclose(out.loc[0, "Age"], 0.5)


def test_export_web_data(tmp_path):
    import json
    from neissai.export import export_web_data
    lab = neissai.add_outcomes(neissai.label_devices(_sample()))
    info = export_web_data(lab, tmp_path, "2026-01-01", "test")
    rec = json.loads((tmp_path / "records.json").read_text())
    stories = json.loads((tmp_path / "stories.json").read_text())
    assert rec["n"] == info["records"] == len(stories)
    assert len(rec["w"]) == rec["n"] and len(rec["cluster_stratum"]) == info["clusters"]
