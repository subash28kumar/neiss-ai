"""Build docs/data/state_estimates.json: expected ED visits for every state, device and year.

For each state (50 + DC), device and year 2020-2025 it stores the AGE-ADJUSTED expected visits
(national estimate for each age group x the state's share of the US population in that age
group) and the SIMPLE expected visits (national estimate x the state's share of the whole US
population), each with a 95% range, plus the age breakdown for e-bikes, e-scooters and bicycles.

Inputs:  docs/data/records.json  (the same records the website uses)
         src/neissai/model/state_population_age.csv  (US Census Bureau, Vintage 2025, SC-EST2025-ALLDATA6)
         src/neissai/model/state_population.csv      (state names)
Run:     PYTHONPATH=src python scripts/build_state_estimates.py
"""
from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from neissai.state import AGE_GROUPS, StateEstimator, load_age_population, us_population

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
MODEL = ROOT / "src" / "neissai" / "model"
AGE_DEVICES = ("E-bike", "E-scooter", "Bicycle")


def main(pop_path: Path = MODEL / "state_population_age.csv", out_path: Path = DOCS / "data" / "state_estimates.json") -> None:
    records = json.loads((DOCS / "data" / "records.json").read_text(encoding="utf-8"))
    pop = load_age_population(pop_path)
    names = {r["abbr"]: r["state"] for r in csv.DictReader((MODEL / "state_population.csv").open(encoding="utf-8"))}
    abbrs = sorted({a for a, _ in pop}, key=lambda a: names[a])
    years = sorted({y for _, y in pop if y in records["years"]})
    out = {
        "updated": records.get("updated") or date.today().isoformat(),   # data date, so rebuilds are stable
        "version": records.get("version"),
        "population_source": "US Census Bureau, Vintage 2025 population estimates by age (SC-EST2025-ALLDATA6), July 1",
        "method": ("Age-adjusted: for each age group, the national NEISS-AI estimate for that age group times the "
                   "state's share of the US population in that age group, summed over age groups. Simple: the "
                   "national estimate times the state's share of the US population. Both are expected numbers, not "
                   "counts; NEISS has no patient-state field. 95% ranges reflect the national sampling uncertainty "
                   "(Taylor linearization, hospitals as clusters within strata)."),
        "age_groups": [g[2] for g in AGE_GROUPS],
        "years": years,
        "devices": records["devices"],
        "fields": ["adj_est", "adj_lo", "adj_hi", "simple_est", "simple_lo", "simple_hi", "national_unstable"],
        "us": {},
        "states": {a: {"name": names[a], "pop": {}, "e": {}, "age": {}} for a in abbrs},
    }
    r0 = lambda v: int(round(v))
    for y in years:
        us = us_population(pop, y)
        out["us"][str(y)] = {"pop": us}
        for dev in records["devices"]:
            est = StateEstimator(records, dev, y)
            nat_unstable = est.estimate([1.0] * len(AGE_GROUPS))["unstable"]   # CPSC rule, national level
            for a in abbrs:
                s = out["states"][a]
                s["pop"][str(y)] = pop[(a, y)]
                r = est.state(pop[(a, y)], us)
                ad, si = r["adjusted"], r["simple"]
                s["e"].setdefault(dev, {})[str(y)] = [r0(ad["est"]), r0(ad["lo"]), r0(ad["hi"]),
                                                      r0(si["est"]), r0(si["lo"]), r0(si["hi"]),
                                                      1 if nat_unstable else 0]
                if dev in AGE_DEVICES:
                    s["age"].setdefault(dev, {})[str(y)] = [[r0(b["est"]), r0(b["lo"]), r0(b["hi"])] for b in r["by_age"]]
    # State forecasts: national forecast (docs/data/forecast.json) x the state's share of national
    # visits in the latest year (age-adjusted). Only the horizons the national method was tested on.
    fpath = DOCS / "data" / "forecast.json"
    if fpath.exists():
        F = json.loads(fpath.read_text(encoding="utf-8"))
        base = max(years)
        tested = F["method"]["tested_years_ahead"]
        out["forecast"] = {"base_year": base, "years": [base + h for h in range(1, tested + 1)],
                           "locked_on": next((l["locked_on"] for l in F.get("locked", []) if l["year"] == base + 1), None),
                           "method": ("National forecast (slowing-growth method, tested on past years) x the state's share "
                                      f"of national visits in {base} (age-adjusted). Assumes each state keeps its {base} share."),
                           "fields": ["central", "lo80", "hi80"]}
        for dev, fd in F["devices"].items():
            nat_base = next(r["est"] for r in fd["actual"] if r["year"] == base)
            rows = {r["year"]: r for r in fd["forecast"] if r["tested"]}
            for a in abbrs:
                st = out["states"][a]
                share = st["e"][dev][str(base)][0] / nat_base
                st.setdefault("fc", {})[dev] = {str(y): [r0(rows[y]["central"] * share), r0(rows[y]["lo80"] * share),
                                                     r0(rows[y]["hi80"] * share)] for y in out["forecast"]["years"]}
    path = Path(out_path)
    path.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {path} ({path.stat().st_size // 1024} KB), {len(abbrs)} states, years {years[0]}-{years[-1]}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--pop", default=str(MODEL / "state_population_age.csv"))
    ap.add_argument("--out", default=str(DOCS / "data" / "state_estimates.json"))
    a = ap.parse_args()
    main(Path(a.pop), Path(a.out))
