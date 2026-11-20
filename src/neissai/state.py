"""Expected emergency department visits for a US state, from national NEISS-AI estimates.

NEISS has no patient-state field, so a state's number can only be EXPECTED, not counted.
Two methods are provided:

* ``simple``       - national estimate x the state's share of the US population.
* ``age-adjusted`` - for each age group, the national estimate for that age group x the
                     state's share of the US population IN THAT AGE GROUP, then summed.
                     A state with more young adults (who ride e-bikes and e-scooters more and
                     get hurt more) gets a higher expected number than its population alone
                     suggests; an older state gets a lower one.

Both assume the state's people in each age group get hurt at the national rate for that age
group. Real state numbers can still differ (how many people ride, where, laws, weather).

Uncertainty: the age-adjusted estimate is a weighted NEISS total in which each record's
weight is multiplied by its age group's state factor (state population / US population in
that group). Its variance therefore uses the same Taylor linearization as every other
NEISS-AI estimate (hospitals as clusters within strata), so the 95% range reflects the
national sampling uncertainty. Population figures are treated as fixed.

Works on the arrays published in ``docs/data/records.json`` so the website, the state
briefs and this module all use the same records.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

Z = 1.959964

#: (first age, last age, label) - the age groups of the Census file SC-EST2025-ALLDATA6.
AGE_GROUPS: List[Tuple[int, int, str]] = [
    (0, 4, "Under 5"), (5, 13, "5-13"), (14, 17, "14-17"), (18, 24, "18-24"),
    (25, 44, "25-44"), (45, 64, "45-64"), (65, 200, "65+"),
]

MODEL = Path(__file__).resolve().parent / "model"


def age_group(age: float) -> int:
    """Index into AGE_GROUPS. NEISS ages are whole years (ages under 1 are stored as 0)."""
    a = 0 if age is None or (isinstance(age, float) and math.isnan(age)) or age < 0 else age
    for i, (lo, hi, _) in enumerate(AGE_GROUPS):
        if lo <= a <= hi:
            return i
    return len(AGE_GROUPS) - 1


def load_age_population(path: Path = MODEL / "state_population_age.csv") -> Dict[Tuple[str, int], List[int]]:
    """{(abbr, year): [population per AGE_GROUPS]} from the bundled CSV."""
    out: Dict[Tuple[str, int], List[int]] = {}
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            key = (r["abbr"], int(r["year"]))
            out.setdefault(key, [0] * len(AGE_GROUPS))
            out[key][[g[2] for g in AGE_GROUPS].index(r["age_group"])] = int(r["population"])
    return out


def _unstable(n: int, est: float, cv: float) -> bool:
    return bool(n < 20 or est < 1200 or (not math.isnan(cv) and cv > 0.33))


class StateEstimator:
    """Pre-sums one device-year so every state's estimate is a quick weighted sum."""

    def __init__(self, records: dict, device: str, year: int):
        self.R = records
        d = records["devices"].index(device)
        y = records["years"].index(year)
        self.cluster_stratum: Sequence[int] = records["cluster_stratum"]
        n_cl, n_g = len(self.cluster_stratum), len(AGE_GROUPS)
        self.S = [[0.0] * n_g for _ in range(n_cl)]   # weighted sum per cluster per age group
        self.T = [0.0] * n_g                           # national total per age group
        self.N = [0] * n_g                             # NEISS records per age group
        for i in range(records["n"]):
            if records["d"][i] != d or records["y"][i] != y:
                continue
            g = age_group(records["a"][i])
            w = records["w"][i]
            self.S[records["c"][i]][g] += w
            self.T[g] += w
            self.N[g] += 1
        self.national = sum(self.T)
        self.records = sum(self.N)

    # -- variance of sum_g f_g * (cluster sums) -----------------------------------------
    def _se(self, factors: Sequence[float]) -> float:
        z = [sum(f * s for f, s in zip(factors, row)) for row in self.S]
        by_stratum: Dict[int, List[float]] = {}
        for c, h in enumerate(self.cluster_stratum):
            by_stratum.setdefault(h, []).append(z[c])
        v = 0.0
        for zs in by_stratum.values():
            n = len(zs)
            if n > 1:
                m = sum(zs) / n
                v += n / (n - 1) * sum((a - m) ** 2 for a in zs)
        return math.sqrt(v)

    def estimate(self, factors: Sequence[float]) -> dict:
        """Weighted total with each age group's weights multiplied by ``factors[g]``."""
        est = sum(f * t for f, t in zip(factors, self.T))
        se = self._se(factors)
        cv = se / est if est > 0 else float("nan")
        return {"est": est, "se": se, "lo": max(est - Z * se, 0.0), "hi": est + Z * se,
                "records": self.records, "unstable": _unstable(self.records, est, cv)}

    def state(self, state_pop: Sequence[int], us_pop: Sequence[int]) -> dict:
        """Age-adjusted and simple expected visits for one state, plus the age breakdown."""
        g = len(AGE_GROUPS)
        f_age = [state_pop[k] / us_pop[k] if us_pop[k] else 0.0 for k in range(g)]
        share = sum(state_pop) / sum(us_pop)
        adj = self.estimate(f_age)
        simple = self.estimate([share] * g)
        by_age = []
        for k in range(g):
            fk = [0.0] * g
            fk[k] = f_age[k]
            e = self.estimate(fk)
            by_age.append({"group": AGE_GROUPS[k][2], "est": e["est"], "lo": e["lo"], "hi": e["hi"],
                           "records": self.N[k], "pop": state_pop[k],
                           "rate": e["est"] / state_pop[k] * 1e5 if state_pop[k] else None})
        pop = sum(state_pop)
        return {"adjusted": adj, "simple": simple, "population": pop,
                "rate_adjusted": adj["est"] / pop * 1e5, "rate_simple": simple["est"] / pop * 1e5,
                "by_age": by_age}


def us_population(pop: Dict[Tuple[str, int], List[int]], year: int) -> List[int]:
    """US total per age group = sum of the 50 states and DC (so states add up to the nation)."""
    tot = [0] * len(AGE_GROUPS)
    for (abbr, y), v in pop.items():
        if y == year:
            tot = [a + b for a, b in zip(tot, v)]
    return tot
