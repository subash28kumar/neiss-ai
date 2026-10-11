"""National estimates from the NEISS sample, with survey-correct 95% confidence intervals.

NEISS is a stratified sample of hospitals (Stratum, PSU = hospital, Weight). Standard errors
use Taylor linearization with hospitals as clusters within strata, the approach CPSC uses.
Estimates are flagged "unstable" when based on fewer than 20 records, when the estimate is
below 1,200, or when the coefficient of variation is above 33% (CPSC's reporting rule).
"""
from __future__ import annotations

from typing import Optional, Sequence

import numpy as np
import pandas as pd

Z = 1.959964


def _stratified_var(df: pd.DataFrame, values: pd.Series) -> float:
    g = (pd.DataFrame({"s": df["Stratum"].values, "p": df["PSU"].values, "y": values.values})
         .groupby(["s", "p"], dropna=False)["y"].sum().reset_index())
    var = 0.0
    for _, h in g.groupby("s", dropna=False):
        n = len(h)
        if n > 1:
            var += n / (n - 1) * float(((h["y"] - h["y"].mean()) ** 2).sum())
    return var


def _unstable(n: int, est: float, cv: float) -> bool:
    return bool(n < 20 or est < 1200 or (not np.isnan(cv) and cv > 0.33))


def total(df: pd.DataFrame, mask: Optional[pd.Series] = None) -> dict:
    """Weighted national total for the records in ``mask`` (all records if None).

    The variance uses the whole sample design, so pass the full table plus a mask
    rather than a filtered table.
    """
    mask = pd.Series(True, index=df.index) if mask is None else mask.reindex(df.index).fillna(False).astype(bool)
    y = df["Weight"].astype(float) * mask.astype(float)
    est = float(y.sum())
    se = float(np.sqrt(_stratified_var(df, y)))
    cv = se / est if est > 0 else np.nan
    n = int(mask.sum())
    return {"estimate": est, "se": se, "ci_low": max(est - Z * se, 0.0), "ci_high": est + Z * se,
            "cv": cv, "records": n, "unstable": _unstable(n, est, cv)}


def proportion(df: pd.DataFrame, numerator: pd.Series, denominator: pd.Series) -> dict:
    """Weighted share of ``denominator`` records that also meet ``numerator`` (ratio estimator)."""
    den = denominator.reindex(df.index).fillna(False).astype(bool)
    num = numerator.reindex(df.index).fillna(False).astype(bool) & den
    w = df["Weight"].astype(float)
    x, y = w * den, w * num
    if x.sum() == 0:
        return {"share": np.nan, "ci_low": np.nan, "ci_high": np.nan, "records": 0}
    r = float(y.sum() / x.sum())
    z = (y - r * x) / x.sum()
    se = float(np.sqrt(_stratified_var(df, z)))
    return {"share": r, "se": se, "ci_low": max(r - Z * se, 0.0), "ci_high": min(r + Z * se, 1.0),
            "records": int(den.sum())}


def national_estimates(df: pd.DataFrame, by: Sequence[str] = ("year", "device"),
                       where: Optional[pd.Series] = None) -> pd.DataFrame:
    """Table of national estimates for every combination of the ``by`` columns.

    ``df`` should be the full design sample (e.g. all micromobility records for the years
    of interest); ``where`` optionally restricts which records are counted.
    """
    base = pd.Series(True, index=df.index) if where is None else where.reindex(df.index).fillna(False).astype(bool)
    rows = []
    keys = df.loc[base, list(by)].drop_duplicates().sort_values(list(by))
    for _, key in keys.iterrows():
        m = base.copy()
        for col in by:
            m &= df[col] == key[col]
        r = total(df, m)
        rows.append({**{c: key[c] for c in by}, **r})
    return pd.DataFrame(rows)


def shares(df: pd.DataFrame, outcome: str, by: Sequence[str] = ("device",),
           where: Optional[pd.Series] = None) -> pd.DataFrame:
    """Weighted share of records with ``outcome == 1`` within each group of ``by``."""
    base = pd.Series(True, index=df.index) if where is None else where.reindex(df.index).fillna(False).astype(bool)
    rows = []
    keys = df.loc[base, list(by)].drop_duplicates().sort_values(list(by))
    for _, key in keys.iterrows():
        m = base.copy()
        for col in by:
            m &= df[col] == key[col]
        r = proportion(df, df[outcome] == 1, m)
        rows.append({**{c: key[c] for c in by}, "outcome": outcome, **r})
    return pd.DataFrame(rows)
