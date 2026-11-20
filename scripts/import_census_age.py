"""Import US Census Bureau state population by age (Vintage 2025, SC-EST2025-ALLDATA6).

Reads the official CSV "Annual State Resident Population Estimates for 6 Race Groups ... by Age,
Sex, and Hispanic Origin: April 1, 2020 to July 1, 2025 (SC-EST2025-ALLDATA6)" from
https://www.census.gov/data/datasets/time-series/demo/popest/2020s-state-detail.html
and writes src/neissai/model/state_population_age.csv: the July 1 resident population of every
state and DC, 2020-2025, in the age groups used by neissai.state.AGE_GROUPS.

The file has one row per state, sex, Hispanic origin, race group and single year of age (85 =
85 and older). We keep SEX = 0 (both sexes) and ORIGIN = 0 (total) and add up the six race
groups, which together cover the whole population.

Checks (the script stops if any fails):
  * every state's total equals the official July 1 total already in
    src/neissai/model/state_population.csv (Vintage 2025, NST-EST2025-POP), for every year;
  * all 51 jurisdictions (50 states and DC) and all years 2020-2025 are present;
  * every age group is positive.

Run: python scripts/import_census_age.py path/to/sc-est2025-alldata6.csv
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src" / "neissai" / "model"
sys.path.insert(0, str(ROOT / "src"))
from neissai.state import AGE_GROUPS, age_group  # noqa: E402

YEARS = range(2020, 2026)
SOURCE = "US Census Bureau, Vintage 2025 estimates SC-EST2025-ALLDATA6 (July 1 resident population)"


def main(src: str) -> None:
    official, abbr_of = {}, {}
    for r in csv.DictReader((MODEL / "state_population.csv").open(encoding="utf-8")):
        official[(r["abbr"], int(r["year"]))] = int(r["population"])
        abbr_of[r["state"]] = r["abbr"]

    pop = defaultdict(lambda: [0] * len(AGE_GROUPS))
    with open(src, encoding="latin-1") as f:
        reader = csv.DictReader(f)
        need = {"NAME", "SEX", "ORIGIN", "RACE", "AGE"} | {f"POPESTIMATE{y}" for y in YEARS}
        if not need <= set(reader.fieldnames or []):
            sys.exit(f"Unexpected layout; missing {sorted(need - set(reader.fieldnames or []))}")
        for r in reader:
            if r["SEX"] != "0" or r["ORIGIN"] != "0" or r["RACE"] not in {"1", "2", "3", "4", "5", "6"}:
                continue
            if r["NAME"] not in abbr_of:
                sys.exit(f"Unknown area {r['NAME']!r}")
            g = age_group(int(r["AGE"]))
            for y in YEARS:
                pop[(abbr_of[r["NAME"]], y)][g] += int(r[f"POPESTIMATE{y}"])

    if len({a for a, _ in pop}) != 51:
        sys.exit(f"Expected 51 states and DC, found {len({a for a, _ in pop})}")
    for key, groups in pop.items():
        if sum(groups) != official[key]:
            sys.exit(f"{key}: age groups add up to {sum(groups):,}, official total is {official[key]:,}")
        if min(groups) <= 0:
            sys.exit(f"{key}: an age group is empty")

    name_of = {v: k for k, v in abbr_of.items()}
    rows = []
    for (a, y), groups in sorted(pop.items(), key=lambda kv: (name_of[kv[0][0]], kv[0][1])):
        for (_, _, label), v in zip(AGE_GROUPS, groups):
            rows.append({"state": name_of[a], "abbr": a, "year": y, "age_group": label, "population": v,
                         "source": SOURCE})
    dst = MODEL / "state_population_age.csv"
    with dst.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {dst}: {len(rows)} rows ({len(pop)} state-years x {len(AGE_GROUPS)} age groups); "
          f"every state-year matches the official July 1 total")


if __name__ == "__main__":
    main(sys.argv[1])
