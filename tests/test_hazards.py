"""Tests for the emerging-hazard scan (neissai.hazards).

Most tests use small synthetic tables. Tests marked "real export" also run against the
Colab export of the full CPSC files when NEISSAI_HAZARD_EXPORT points to that folder
(clusters.csv, psu.csv, terms.csv); otherwise they are skipped.
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import neissai
from neissai import hazards as hz
from neissai.io import standardize

EXPORT = os.environ.get("NEISSAI_HAZARD_EXPORT", "")
real = pytest.mark.skipif(not (EXPORT and (Path(EXPORT) / "clusters.csv").exists()),
                          reason="set NEISSAI_HAZARD_EXPORT to the Colab export folder")


# --- synthetic data -------------------------------------------------------------------------
def _records(seed=1, n=3000):
    rng = np.random.default_rng(seed)
    strata = rng.choice(["S", "M", "V"], n)
    psu = np.array([f"{s}{rng.integers(1, 6)}" for s in strata])
    codes = rng.choice(["5040", "1807", "3215", "1333"], n, p=[0.3, 0.5, 0.05, 0.15])
    df = pd.DataFrame({"Product_1": codes, "Product_2": np.where(rng.random(n) < 0.1, "1807", "0"),
                       "Product_3": "0", "Narrative_1": "TEST", "Stratum": strata, "PSU": psu,
                       "Weight": rng.uniform(5, 120, n).round(4), "Age": "30",
                       "Disposition": rng.choice(["1", "4"], n, p=[0.85, 0.15])})
    df["Body_Part"] = "75"
    df["Alcohol"] = "0"
    df["Treatment_Date"] = "03/15/2025"
    # one hospital with no 3215 records at all: a zero cell that must count in the variance
    df.loc[df["PSU"] == "V5", ["Product_1", "Product_2"]] = ["1807", "0"]
    return standardize(df, 2025)


def _export(products, years=(2023, 2024, 2025), hospitals=12, seed=3):
    """Cluster table: products = {code: {year: mean records per hospital}}; weight 50 per record."""
    rng = np.random.default_rng(seed)
    rows, psu = [], []
    for y in years:
        for h in range(hospitals):
            s = "ABC"[h % 3]
            psu.append({"year": y, "Stratum": s, "PSU": str(100 + h)})
            tot_n = tot_w = 0
            for code, by_year in products.items():
                mu = by_year.get(y, 0)
                if mu == 0:
                    continue
                n = int(rng.poisson(mu))
                if n == 0:
                    continue
                w = 50.0 * n
                rows.append({"product": code, "year": y, "month": 6, "Stratum": s, "PSU": str(100 + h),
                             "n": n, "w": w, "n_hosp": n // 5, "w_hosp": 50.0 * (n // 5)})
                tot_n += n
                tot_w += w
            rows.append({"product": "0", "year": y, "month": 6, "Stratum": s, "PSU": str(100 + h),
                         "n": tot_n, "w": tot_w, "n_hosp": tot_n // 5, "w_hosp": 50.0 * (tot_n // 5)})
    return {"clusters": hz._clean_clusters(pd.DataFrame(rows)), "psu": pd.DataFrame(psu)}


# --- totals ---------------------------------------------------------------------------------
def test_totals_match_package_total():
    df = _records()
    clusters, psu = hz.clusters_from_records(df, hospitalized="Disposition")
    clusters["n_hosp"] = 0
    data = {"clusters": clusters, "psu": psu}
    tab = hz.period_totals(data, 2025).set_index("product")
    codes = df[["Product_1", "Product_2", "Product_3"]]
    for code in ["5040", "1807", "3215", "1333"]:
        direct = neissai.total(df, codes.isin([code]).any(axis=1))
        assert np.isclose(tab.loc[code, "estimate"], direct["estimate"])
        assert np.isclose(tab.loc[code, "se"], direct["se"])          # zero-count hospitals included
        assert tab.loc[code, "records"] == direct["records"]
        assert bool(tab.loc[code, "unstable"]) == direct["unstable"]
    assert np.isclose(tab.loc["0", "estimate"], df["Weight"].sum())


@real
def test_real_export_bicycles_2025():
    data = hz.read_hazard_export(EXPORT)
    t = hz.period_totals(data, 2025, products=["5040", "5045", "0"]).set_index("product")
    assert round(t.loc["5040", "estimate"]) == 420962
    assert round(t.loc["5040", "se"]) == 38649
    assert round(t.loc["5045", "estimate"], -2) == 102600
    assert t.loc["0", "records"] == 410201
    assert int(hz.records_by_year(data).sum()) == 2442011


# --- excess change --------------------------------------------------------------------------
def test_uniform_weight_jump_flags_nothing():
    data = _export({"1807": {2024: 200}, "5040": {2024: 60}}, years=(2024, 2025))
    c = data["clusters"]
    same = c[c["year"] == 2024].assign(year=2025)          # same records in 2025 ...
    same[["w", "w_hosp"]] *= 2                              # ... but every weight doubles (a reweighting year)
    data["clusters"] = pd.concat([c[c["year"] == 2024], same], ignore_index=True)
    r = hz.compare(data, 2025)
    x = r[r["product"] == "5040"]
    assert np.allclose(x["excess"], 0, atol=1e-6)
    assert (x["pct_change"] > 0.5).all()           # the plain change looks like a big rise
    assert not r["flag"].any()


def test_real_rise_is_flagged_with_mdc_and_fdr():
    data = _export({"1807": {2024: 400, 2025: 400}, "5045": {2024: 30, 2025: 90}, "5040": {2024: 60, 2025: 60}})
    r = hz.compare(data, 2025).set_index(["measure", "product"])
    e = r.loc[("ed_visits", "5045")]
    assert e["flag"] and e["excess"] >= e["mdc80"] and e["q"] < 0.05
    assert not r.loc[("ed_visits", "5040"), "flag"]
    assert r.loc[("ed_visits", "0"), "status"] == "all NEISS (reference)"


def test_bh_qvalues():
    q = hz.bh_qvalues([0.01, 0.04, 0.03, np.nan, 0.5])
    assert np.allclose(q[[0, 1, 2, 4]], [0.04, 0.04 * 4 / 3, 0.04 * 4 / 3, 0.5])
    assert np.isnan(q[3])


# --- code groups and code changes ------------------------------------------------------------
def test_code_group_only_when_codes_change():
    data = _export({"0001": {2023: 300, 2024: 300, 2025: 300},
                    "3215": {2023: 40}, "5045": {2024: 25, 2025: 40}, "5046": {2024: 20, 2025: 20}})
    g24 = hz.groups_for(data, 2024, 2023)
    assert [g.id for g in g24] == ["3215+5045+5046"]
    assert hz.groups_for(data, 2025, 2024) == []
    r = hz.compare(data, 2024).set_index(["measure", "product"])
    assert r.loc[("ed_visits", "3215+5045+5046"), "status"].startswith("code group")
    assert r.loc[("ed_visits", "5045"), "status"] == "in code group 3215+5045+5046"
    assert not r.loc[("ed_visits", "5045"), "flag"]      # a new code is never a hazard flag by itself
    grp = r.loc[("ed_visits", "3215+5045+5046")]
    assert np.isclose(grp["estimate"], r.loc[("ed_visits", "5045"), "estimate"] + r.loc[("ed_visits", "5046"), "estimate"])
    r25 = hz.compare(data, 2025)
    assert "3215+5045+5046" not in set(r25["product"])   # no code change 2024 -> 2025: codes compared one by one


def test_code_change_detection():
    data = _export({"0001": {2023: 300, 2024: 300, 2025: 300}, "7001": {2023: 10, 2024: 10},
                    "7002": {2024: 0, 2025: 10}, "9999": {2023: 1, 2025: 0.2}})
    t = hz.code_timeline(data).set_index("product")
    assert t.loc["7001", "ends"] and t.loc["7001", "last_year"] == 2024
    assert t.loc["7002", "starts"] and t.loc["7002", "first_year"] == 2025
    assert not t.loc["9999", "possible_code_change"]     # rare code: too few records to call it a change
    s = hz.suggest_code_groups(data)
    row = s[s["year"] == 2025].iloc[0]
    assert row["codes_ended"] == "7001" and row["codes_started"] == "7002" and not row["covered_by_known_group"]
    r = hz.compare(data, 2025).set_index(["measure", "product"])
    assert r.loc[("ed_visits", "7002"), "status"].startswith("new code")
    assert not r.loc[("ed_visits", "7002"), "flag"]


@real
def test_real_export_code_changes_found_automatically():
    data = hz.read_hazard_export(EXPORT)
    s = hz.suggest_code_groups(data).set_index("year")
    assert s.loc[2024, "codes_ended"] == "3215" and s.loc[2024, "codes_started"] == "5045 5046"
    assert s.loc[2020, "codes_ended"] == "1329 5042" and s.loc[2020, "codes_started"] == "5022 5023 5024 5025"
    assert s.loc[2021, "codes_ended"] == "1543 1545" and s.loc[2021, "codes_started"] == "1552"
    assert s["covered_by_known_group"].all()


# --- labels ---------------------------------------------------------------------------------
def test_labels_pandemic_and_2024():
    data = _export({"0001": {2020: 100, 2021: 100, 2023: 100, 2024: 100}}, years=(2020, 2021, 2023, 2024))
    assert (hz.compare(data, 2021)["note"].str.contains("pandemic")).all()
    assert (hz.compare(data, 2024, 2023)["note"].str.contains("weights rose")).all()


def test_admissions_use_hospital_columns():
    data = _export({"0001": {2024: 100, 2025: 100}})
    r = hz.compare(data, 2025).set_index(["measure", "product"])
    c = data["clusters"]
    assert np.isclose(r.loc[("admissions", "0001"), "estimate"], c[(c["year"] == 2025) & (c["product"] == "0001")]["w_hosp"].sum())


# --- emerging terms -------------------------------------------------------------------------
def test_term_category():
    assert hz.term_category("PT FELL") == "writing style"
    assert hz.term_category("14YOM") == "writing style"
    assert hz.term_category("DX") == "writing style"
    assert hz.term_category("STATED") == "writing style"
    assert hz.term_category("LEFT KNEE") == "clinical or context wording"
    assert hz.term_category("E-BIKE") == "candidate"
    assert hz.term_category("WATER BEADS") == "candidate"
    assert hz.likely_misspelling("INJRUED", {"INJURED": 5000}) == "INJURED"
    assert hz.likely_misspelling("FALLS", {"FALL": 5000}) is None
    assert hz.likely_misspelling("EEBIKE", {"EBIKE": 5000}) is None


def test_emerging_terms():
    rng = np.random.default_rng(0)
    rows = []
    for i in range(400):  # ordinary words drift a little
        base = int(rng.integers(300, 3000))
        rows += [(f"WORD{chr(65 + i % 26)}{i}", 2024, base), (f"WORD{chr(65 + i % 26)}{i}", 2025, int(base * rng.normal(1.1, 0.05)))]
    rows += [("WATER BEADS", 2024, 40), ("WATER BEADS", 2025, 400),   # emerging hazard word
             ("PT STATED", 2024, 40), ("PT STATED", 2025, 400),       # writing style
             ("NEWTHING", 2025, 60)]                                  # new term, below the export floor before
    terms = pd.DataFrame(rows, columns=["term", "year", "n"]).assign(w=lambda d: d["n"] * 40.0)
    records = pd.Series({2024: 100000, 2025: 110000})
    e = hz.emerging_terms(terms, 2025, records).set_index("term")
    assert e.loc["WATER BEADS", "flag"] and e.loc["NEWTHING", "flag"] and e.loc["NEWTHING", "new_term"]
    assert not e.loc["PT STATED", "flag"] and e.loc["PT STATED", "category"] == "writing style"
    assert e["flag"].sum() == 2


def test_product_word_merges_device_spellings():
    from neissai.hazards import product_word
    assert product_word("ELECTRIC BICYCLE") == "E-BIKE"
    assert product_word("RIDING EBIKE") == "E-BIKE"
    assert product_word("ELECTRIC SCOOTER") == "E-SCOOTER"
    assert product_word("WATER BEADS") == "WATER BEADS"
    assert product_word("PAIN SAYS") == ""


def test_hazard_words_keeps_one_row_per_device():
    import pandas as pd
    from neissai.hazards import hazard_words
    et = pd.DataFrame({"term": ["E-BIKE", "ELECTRIC BICYCLE", "PAIN SAYS", "TRAMPOLINE PARK"],
                       "flag": [True, True, True, False], "z_robust": [5.0, 4.0, 9.0, 8.0]})
    hw = hazard_words(et)
    assert list(hw["term"]) == ["E-BIKE"]
    assert int(hw.loc[0, "related_terms"]) == 1


def test_every_product_code_in_data_has_a_name():
    from neissai.hazards import PRODUCT_NAMES
    for code in ["5040", "5045", "5022", "3215", "1807", "897", "1550"]:
        assert PRODUCT_NAMES.get(code), code


def test_narrative_terms_drop_stopwords_and_pair_words():
    from neissai.hazards import narrative_terms
    t = narrative_terms("14YOM FELL OFF THE E-BIKE TO THE FLOOR")
    assert {"FELL", "E-BIKE", "FLOOR", "FELL E-BIKE", "E-BIKE FLOOR"} <= t
    assert "THE" not in t and "OFF" not in t


def test_build_hazard_export_round_trip(tmp_path):
    import pandas as pd
    from neissai.hazards import build_hazard_export, read_hazard_export, period_totals
    recs = pd.DataFrame({
        "Treatment_Date": ["2024-01-05", "2024-02-05", "2025-03-01", "2025-03-02"] * 6,
        "year": [2024, 2024, 2025, 2025] * 6,
        "Product_1": ["5045", "5040", "5045", "5045"] * 6, "Product_2": "0", "Product_3": "0",
        "Disposition": ["1", "4 - Treated and admitted", "1", "2"] * 6,
        "Stratum": ["S", "S", "V", "V"] * 6, "PSU": [str(i % 4) for i in range(24)],
        "Weight": [10.0, 20.0, 30.0, 40.0] * 6,
        "Narrative": ["RIDING E-BIKE FELL", "FELL OFF BICYCLE", "E-BIKE CRASH", "E-BIKE HIT BY CAR"] * 6,
    })
    out = build_hazard_export(recs, tmp_path / "exp")
    data = read_hazard_export(out)
    t25 = period_totals(data, 2025).set_index("product")
    assert abs(t25.loc["5045", "estimate"] - 6 * (30 + 40)) < 1e-6
    a25 = period_totals(data, 2025, measure="admissions").set_index("product")
    assert abs(a25.loc["5045", "estimate"] - 6 * 40) < 1e-6  # disposition 2 = transferred
    a24 = period_totals(data, 2024, measure="admissions").set_index("product")
    assert abs(a24.loc["5040", "estimate"] - 6 * 20) < 1e-6  # text disposition '4 - ...'
    terms = pd.read_csv(out / "terms.csv")
    assert int(terms[(terms.term == "E-BIKE") & (terms.year == 2025)]["n"].iloc[0]) == 12


def test_update_site_hazards_writes_summary(tmp_path):
    import json
    import pandas as pd
    from neissai.hazards import update_site_hazards
    rows = []
    for year, n_ebike in ((2024, 30), (2025, 90)):
        for i in range(200):
            prod = "5045" if i < n_ebike else "5040"
            rows.append({"Treatment_Date": f"{year}-0{1 + i % 9}-10", "year": year, "Product_1": prod,
                         "Product_2": "0", "Product_3": "0", "Disposition": "1",
                         "Stratum": "SMLV"[i % 4], "PSU": str(i % 40), "Weight": 50.0,
                         "Narrative": "RIDING E-BIKE FELL" if prod == "5045" else "FELL OFF BICYCLE"})
    summary = update_site_hazards(pd.DataFrame(rows), tmp_path / "hz", tmp_path / "work")
    saved = json.loads((tmp_path / "hz" / "summary.json").read_text())
    assert saved["year"] == 2025 and saved["base_year"] == 2024
    assert summary == saved
    assert (tmp_path / "hz" / "hazard_scan_2025.csv").exists()


def test_signal_status_rules():
    from neissai.hazards import signal_status
    assert signal_status({"note": "large 2025 jump, likely coding practice", "records": 900}) == "Coding"
    assert signal_status({"note": "", "unstable_base": True, "records": 900}) == "Check"
    assert signal_status({"note": "", "unstable_base": False, "records": 40}) == "Check"
    assert signal_status({"note": "", "unstable_base": False, "records": 900}) == "Signal"
