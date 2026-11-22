"""'Compare your state' workbooks: expected visits by age add up to the nation and match the site."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REC = ROOT / "docs" / "data" / "records.json"
pytestmark = pytest.mark.skipif(not REC.exists(), reason="records.json not built")


def _mod():
    spec = importlib.util.spec_from_file_location("bsb", ROOT / "scripts" / "build_state_benchmarks.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_expected_by_age_sums_to_national_and_matches_site():
    m = _mod()
    from neissai.state import load_age_population, us_population
    records = json.loads(REC.read_text())
    pop = load_age_population()
    year = 2025
    us = us_population(pop, year)
    nat = m.national_by_age(records, year, us)
    states = sorted({a for a, y in pop if y == year})
    site = json.loads((ROOT / "docs" / "data" / "state_estimates.json").read_text())["states"]
    for dev in m.DEVICES:
        for k, g in enumerate(nat[dev]["groups"]):
            tot = sum(g["rate"] * pop[(a, year)][k] / 1e5 for a in states)
            assert abs(tot - g["est"]) < 1e-6 * max(1, g["est"]) + 1e-6
        ma = [round(g["rate"] * pop[("MA", year)][k] / 1e5) for k, g in enumerate(nat[dev]["groups"])]
        assert ma == [row[0] for row in site["MA"]["age"][dev][str(year)]]


def test_workbook_plain_words_worked_example_and_all_ages_guard(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    m = _mod()
    from neissai.state import load_age_population, us_population
    records = json.loads(REC.read_text())
    pop = load_age_population()
    year = 2025
    nat = m.national_by_age(records, year, us_population(pop, year))
    path = tmp_path / "ma.xlsx"
    m.workbook("MA", "Massachusetts", year, nat, pop[("MA", year)], "test", path)
    wb = openpyxl.load_workbook(path)
    ws = wb["Compare"]
    heads = [ws.cell(6, c).value for c in range(1, 13)]
    assert heads[6] == "Benchmark: visits in Massachusetts at the US rate"
    assert not any("xpected" in str(h) for h in heads)
    # All-ages ratio only once every age group is filled in
    all_row = next(r for r in range(7, 40) if ws.cell(r, 1).value == "E-bike" and ws.cell(r, 2).value == "All ages")
    f = ws.cell(all_row, 10).value
    assert "fill in all age groups" in f and "<7" in f
    # worked example uses the same numbers as the 25-44 e-bike row
    row = next(r for r in range(7, 40) if ws.cell(r, 1).value == "E-bike" and ws.cell(r, 2).value == "25-44")
    text = " ".join(str(c.value) for c in wb["How to use"]["A"] if c.value)
    assert f"{ws.cell(row, 7).value:,} visits: the benchmark" in text
    assert ws.cell(row, 8).value.replace(" - ", " to ") in text
    assert "Taylor" not in text.split("Technical note")[0]


def test_site_compare_box_matches_workbook_numbers():
    tpl = (ROOT / "docs" / "template.html").read_text(encoding="utf-8")
    assert 'id="stcmp"' in tpl and "fill in all age groups" in tpl and ".reqbox[hidden]{display:none}" in tpl
    site = json.loads((ROOT / "docs" / "data" / "state_estimates.json").read_text())
    ma = site["states"]["MA"]["age"]["E-bike"]["2025"]
    assert site["age_groups"][4] == "25-44" and ma[4] == [656, 402, 910]


def test_state_cyclist_deaths_file_matches_nhtsa_totals():
    d = json.loads((ROOT / "docs" / "data" / "state_cyclist_deaths.json").read_text())
    assert len(d["states"]) == 51 and d["year"] >= 2024
    assert sum(v["deaths"] for v in d["states"].values()) == d["us"]["deaths"]
    assert sum(v["traffic_deaths"] for v in d["states"].values()) == d["us"]["traffic_deaths"]
    assert 700 < d["us"]["deaths"] < 2000


def test_state_bike_commute_file():
    d = json.loads((ROOT / "docs" / "data" / "state_bike_commute.json").read_text())
    assert len(d["states"]) == 51 and d["year"] >= 2025
    assert sum(v["bicycle"] for v in d["states"].values()) == d["us"]["bicycle"]
    for v in d["states"].values():
        assert abs(v["share_pct"] - 100 * v["bicycle"] / v["workers"]) < 0.01


def test_medical_cost_file():
    d = json.loads((ROOT / "docs" / "data" / "injury_medical_costs.json").read_text())
    assert d["cost_2015_usd"] == {"road_crash_with_motor_vehicle": 14193, "other_bicycle_injury": 6109}
    f = d["price_update"]["factor"]
    assert 1.25 < f < 1.35
    latest = d["price_update"].get("index_latest_avg", d["price_update"].get("index_2025_avg"))
    assert d["cost_2025_usd"]["road_crash_with_motor_vehicle"] == round(14193 * latest / d["price_update"]["index_2015_avg"])


def test_refresh_context_script_imports_and_maps_51_states():
    import importlib.util
    spec = importlib.util.spec_from_file_location("rc", ROOT / "scripts" / "refresh_context.py")
    rc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rc)
    assert len(rc.FIPS) == 51 and rc.FIPS["11"] == "DC" and rc.FIPS["06"] == "CA"


def test_state_pages_and_sitemap():
    import importlib.util, re
    spec = importlib.util.spec_from_file_location("bsp", ROOT / "scripts" / "build_state_pages.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.main()
    pages = list((ROOT / "docs" / "states").glob("*.html"))
    assert len(pages) == 52  # 51 states + index
    sm = (ROOT / "docs" / "sitemap.xml").read_text()
    assert sm.count("<loc>") == 54 and "states/massachusetts.html" in sm
    S = json.loads((ROOT / "docs" / "data" / "state_estimates.json").read_text())
    ma = S["states"]["MA"]["e"]["E-bike"]["2025"][0]
    page = (ROOT / "docs" / "states" / "massachusetts.html").read_text()
    assert f"about <b>{m.fmt(ma)}</b>\nwould have gone to an emergency room" in page and "expected numbers, not counts" in page
    ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', page).group(1))
    assert ld["@type"] == "Dataset" and ld["spatialCoverage"]["name"].startswith("Massachusetts")
