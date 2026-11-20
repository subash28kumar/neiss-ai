"""Short-term forecasts of national emergency department visits, tested on past years.

Method ("slowing growth", a damped trend on the log scale):
    growth next year = average yearly growth over the last 3 years x phi
    growth the year after = that x phi again, and so on.
With phi below 1 growth fades year by year, as it does for most new products. The central
phi is chosen by a back-test: pretend to stand in 2022, 2023 and 2024, forecast the years after,
and compare with what NEISS actually showed, pooled over six devices (e-bike, e-scooter, kick
scooter, bicycle, hoverboard, skateboard). Ranges come from the back-test errors at each horizon
(log scale, widening with the square root of the horizon), so their width is earned, not assumed.

Forecasts more than 3 years ahead cannot be back-tested with the years available and are
labelled scenarios. Forecasts describe where recent trends point; they cannot predict the
effect of a specific law.
"""
from __future__ import annotations

import math
from typing import Dict, List, Sequence

PHI_GRID = (0.3, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95)
BACKTEST_DEVICES = ("E-bike", "E-scooter", "Kick scooter", "Bicycle", "Hoverboard", "Skateboard")
Z80 = 1.2816


def damped(values: Sequence[float], phi: float, horizon: int, window: int = 3) -> List[float]:
    """Forecast ``horizon`` years after the last value with a damped log-growth trend."""
    logs = [math.log(v) for v in values]
    steps = [b - a for a, b in zip(logs, logs[1:])][-window:]
    g = sum(steps) / len(steps)
    out, cur = [], logs[-1]
    for t in range(1, horizon + 1):
        cur += g * phi ** t
        out.append(math.exp(cur))
    return out


def series(by_device: List[dict], device: str) -> Dict[int, float]:
    return {r["year"]: float(r["est"]) for r in by_device if r["device"] == device}


def backtest(by_device: List[dict], phi: float, devices: Sequence[str] = BACKTEST_DEVICES,
             first_cut: int | None = None) -> List[dict]:
    """Every (device, cut-off year, horizon) forecast that can be checked against a later year."""
    out = []
    for dev in devices:
        s = series(by_device, dev)
        years = sorted(s)
        last = years[-1]
        cuts = [y for y in years if y >= (first_cut or years[0] + 3) and y < last]
        for cut in cuts:
            hist = [s[y] for y in years if y <= cut]
            if len(hist) < 4:
                continue
            f = damped(hist, phi, last - cut)
            for h in range(1, last - cut + 1):
                out.append({"device": dev, "cut": cut, "h": h, "year": cut + h,
                            "forecast": f[h - 1], "actual": s[cut + h],
                            "log_error": math.log(f[h - 1] / s[cut + h])})
    return out


def choose_phi(by_device: List[dict], grid: Sequence[float] = PHI_GRID, first_cut: int = 2022) -> dict:
    """Pick phi from the pooled back-test with the "one-standard-error rule".

    Several phi values score almost the same on so few years, so the best score alone is not a
    reliable choice. We take the most cautious phi (strongest slowing) whose mean absolute log
    error is within one standard error of the best one - a standard way to avoid over-fitting.
    """
    scores, ses = {}, {}
    for phi in grid:
        errs = [abs(r["log_error"]) for r in backtest(by_device, phi, first_cut=first_cut)]
        m = sum(errs) / len(errs)
        sd = math.sqrt(sum((e - m) ** 2 for e in errs) / (len(errs) - 1))
        scores[phi], ses[phi] = m, sd / math.sqrt(len(errs))
    best = min(scores, key=scores.get)
    limit = scores[best] + ses[best]
    chosen = min(phi for phi in grid if scores[phi] <= limit)
    return {"phi": chosen, "best_phi": best, "scores": scores, "limit": limit}


def error_scale(bt: List[dict]) -> float:
    """Spread of 1-year-equivalent log errors (each error divided by sqrt(horizon)), root mean square."""
    z = [r["log_error"] / math.sqrt(r["h"]) for r in bt]
    return math.sqrt(sum(v * v for v in z) / len(z))


def summarize_backtest(bt: List[dict], sigma1: float) -> List[dict]:
    rows = []
    for h in sorted({r["h"] for r in bt}):
        rs = [r for r in bt if r["h"] == h]
        miss = sorted(abs(math.exp(r["log_error"]) - 1) for r in rs)
        inside = sum(abs(r["log_error"]) <= Z80 * sigma1 * math.sqrt(h) for r in rs)
        rows.append({"years_ahead": h, "forecasts": len(rs), "median_miss": miss[len(miss) // 2],
                     "mean_miss": sum(miss) / len(miss), "inside_80": inside})
    return rows


def forecast(values: Sequence[float], phi: float, sigma1: float, horizon: int = 5,
             slow_phi: float = 0.6, fast_phi: float = 0.95) -> List[dict]:
    cen = damped(values, phi, horizon)
    slow = damped(values, slow_phi, horizon)
    fast = damped(values, fast_phi, horizon)
    out = []
    for h in range(1, horizon + 1):
        s = sigma1 * math.sqrt(h)
        out.append({"h": h, "central": cen[h - 1], "lo80": cen[h - 1] * math.exp(-Z80 * s),
                    "hi80": cen[h - 1] * math.exp(Z80 * s), "slower": slow[h - 1], "faster": fast[h - 1]})
    return out
