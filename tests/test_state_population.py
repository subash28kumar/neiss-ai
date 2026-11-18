"""State populations used by the 'Your state' view must add up exactly to the US totals."""
import csv
from collections import defaultdict
from pathlib import Path

MODEL = Path(__file__).resolve().parents[1] / "src" / "neissai" / "model"


def test_states_sum_to_us_total():
    states = list(csv.DictReader((MODEL / "state_population.csv").open(encoding="utf-8")))
    us = {r["year"]: int(r["population"]) for r in csv.DictReader((MODEL / "us_population.csv").open(encoding="utf-8"))}
    total = defaultdict(int)
    names = defaultdict(set)
    for r in states:
        total[r["year"]] += int(r["population"])
        names[r["year"]].add(r["abbr"])
    assert sorted(total) == [str(y) for y in range(2020, 2026)]
    for y, t in total.items():
        assert len(names[y]) == 51  # 50 states + DC
        assert t == us[y]
