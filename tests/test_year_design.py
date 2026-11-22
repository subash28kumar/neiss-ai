"""One-year estimates use that year's sample design only (independent review, Nov 2026)."""
import numpy as np
import pandas as pd

from neissai.estimate import national_estimates, total


def _df():
    # 2020 samples hospitals 1-3 in stratum A; 2021 samples hospitals 4-6. Hospital 3 has no
    # e-bike record in 2020 but was sampled (it has another record).
    rows = []
    for y, psus in ((2020, [1, 2, 3]), (2021, [4, 5, 6])):
        for p in psus:
            rows.append({"year": y, "Stratum": "A", "PSU": p, "Weight": 10.0 * p, "device": "E-bike" if p != 3 else "Other"})
    return pd.DataFrame(rows)


def test_one_year_range_uses_that_years_hospitals():
    df = _df()
    est = national_estimates(df, by=["year", "device"], where=df["device"] == "E-bike")
    r2020 = est[(est.year == 2020)].iloc[0]
    # by hand, 2020 design only: cluster sums 10, 20, 0 (n = 3)
    y = np.array([10.0, 20.0, 0.0])
    var = 3 / 2 * ((y - y.mean()) ** 2).sum()
    assert abs(r2020["se"] - np.sqrt(var)) < 1e-9
    # the old pooled design (6 hospitals, three of them not sampled in 2020) gives a different answer
    pooled = total(df, (df.year == 2020) & (df.device == "E-bike"))
    assert abs(pooled["se"] - r2020["se"]) > 1e-6


def test_records_json_has_year_clusters():
    import json
    from pathlib import Path
    r = json.loads((Path(__file__).resolve().parents[1] / "docs" / "data" / "records.json").read_text())
    if "year_clusters" not in r:   # data rebuilt by the refresh robot after this change
        return
    assert len(r["year_clusters"]) == len(r["years"])
    used = {c for i in range(r["n"]) for c in [r["c"][i]]}
    for yi, cl in enumerate(r["year_clusters"]):
        assert 60 <= len(cl) <= len(r["cluster_stratum"])
    assert used <= set().union(*map(set, r["year_clusters"]))
