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
