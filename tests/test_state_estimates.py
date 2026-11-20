"""Checks for the age-adjusted state estimates (neissai.state)."""
import json
import math
from pathlib import Path

import pytest

from neissai.state import AGE_GROUPS, StateEstimator, age_group, load_age_population, us_population

ROOT = Path(__file__).resolve().parents[1]
RECORDS = ROOT / "docs" / "data" / "records.json"
DATA = ROOT / "docs" / "data.json"
AGE_POP = ROOT / "src" / "neissai" / "model" / "state_population_age.csv"
STATE_POP = ROOT / "src" / "neissai" / "model" / "state_population.csv"


@pytest.fixture(scope="module")
def records():
    if not RECORDS.exists():
        pytest.skip("records.json not built")
    return json.loads(RECORDS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ebike2025(records):
    return StateEstimator(records, "E-bike", 2025)


def test_age_groups_cover_every_age_once():
    for a in range(0, 121):
        hits = [i for i, (lo, hi, _) in enumerate(AGE_GROUPS) if lo <= a <= hi]
        assert len(hits) == 1 and age_group(a) == hits[0]
    assert age_group(-1) == 0 and age_group(float("nan")) == 0


def test_national_total_matches_published_estimate(ebike2025):
    pub = {(r["device"], r["year"]): r for r in json.loads(DATA.read_text())["by_device"]}[("E-bike", 2025)]
    assert round(ebike2025.national) == pub["est"]
    nat = ebike2025.estimate([1.0] * len(AGE_GROUPS))
    assert round(nat["lo"]) == pub["lo"] and round(nat["hi"]) == pub["hi"]


def test_same_age_mix_gives_same_answer_as_simple_method(ebike2025):
    us = [1_000_000 * (k + 1) for k in range(len(AGE_GROUPS))]
    state = [round(v * 0.03) for v in us]          # exactly 3% of every age group
    r = ebike2025.state(state, us)
    assert math.isclose(r["adjusted"]["est"], r["simple"]["est"], rel_tol=1e-9)
    assert math.isclose(r["adjusted"]["se"], r["simple"]["se"], rel_tol=1e-9)


def test_simple_method_is_national_times_population_share(ebike2025):
    us = [10] * len(AGE_GROUPS)
    state = [1] * len(AGE_GROUPS)
    r = ebike2025.state(state, us)
    nat = ebike2025.estimate([1.0] * len(AGE_GROUPS))
    assert math.isclose(r["simple"]["est"], nat["est"] * 0.1, rel_tol=1e-12)
    assert math.isclose(r["simple"]["se"], nat["se"] * 0.1, rel_tol=1e-12)


def test_younger_state_gets_more_than_older_state(ebike2025):
    """Two halves of one country: the younger half must get the larger share of e-bike visits."""
    g = len(AGE_GROUPS)
    young = [3, 3, 3, 3, 3, 1, 1][:g]
    old = [1, 1, 1, 1, 1, 3, 3][:g]
    us = [a + b for a, b in zip(young, old)]
    ry, ro = ebike2025.state(young, us), ebike2025.state(old, us)
    assert ry["adjusted"]["est"] > ro["adjusted"]["est"]
    assert math.isclose(ry["adjusted"]["est"] + ro["adjusted"]["est"], ebike2025.national, rel_tol=1e-9)


def test_age_breakdown_adds_up(ebike2025):
    us = [7, 9, 4, 6, 20, 18, 12]
    st = [1, 2, 1, 1, 3, 2, 2]
    r = ebike2025.state(st, us)
    assert math.isclose(sum(b["est"] for b in r["by_age"]), r["adjusted"]["est"], rel_tol=1e-9)


@pytest.mark.skipif(not AGE_POP.exists(), reason="state_population_age.csv not imported yet")
def test_real_population_file(records):
    import csv
    pop = load_age_population(AGE_POP)
    totals = {}
    for r in csv.DictReader(STATE_POP.open(encoding="utf-8")):
        totals[(r["abbr"], int(r["year"]))] = int(r["population"])
    years = sorted({y for _, y in pop})
    assert years == list(range(2020, 2026))
    for key, groups in pop.items():
        assert len(groups) == len(AGE_GROUPS) and min(groups) > 0
        assert sum(groups) == totals[key], key        # age groups add up to the official state total
    assert len({a for a, _ in pop}) == 51
    # every state's age-adjusted estimates add up to the national estimate
    est = StateEstimator(records, "E-bike", 2025)
    us = us_population(pop, 2025)
    s = sum(est.state(pop[(a, 2025)], us)["adjusted"]["est"] for a in {a for a, _ in pop})
    assert math.isclose(s, est.national, rel_tol=1e-9)
