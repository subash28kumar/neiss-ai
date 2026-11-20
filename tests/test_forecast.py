"""Checks for the forecast module and the locked-forecast file."""
import json
import math
from pathlib import Path

from neissai.forecast import backtest, choose_phi, damped, error_scale, forecast, summarize_backtest

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "docs" / "data.json").read_text(encoding="utf-8"))["by_device"]


def test_damped_trend_math():
    # constant 50% growth; phi = 1 keeps it, phi = 0 stops it
    v = [100, 150, 225, 337.5]
    assert all(math.isclose(a, b) for a, b in zip(damped(v, 1.0, 2), [506.25, 759.375]))
    assert all(math.isclose(a, 337.5) for a in damped(v, 0.0, 3))
    f = damped(v, 0.5, 2)
    assert math.isclose(f[0], 337.5 * 1.5 ** 0.5) and math.isclose(f[1], f[0] * 1.5 ** 0.25)


def test_backtest_never_peeks_at_the_future():
    for r in backtest(DATA, 0.8, first_cut=2022):
        assert r["year"] == r["cut"] + r["h"] and r["cut"] < r["year"]
        hist = sorted(x["est"] for x in DATA if x["device"] == r["device"] and x["year"] <= r["cut"])
        assert len(hist) >= 4


def test_phi_choice_and_ranges_are_honest():
    pick = choose_phi(DATA, first_cut=2022)
    assert pick["scores"][pick["phi"]] <= pick["limit"] and pick["phi"] <= pick["best_phi"]
    bt = backtest(DATA, pick["phi"], first_cut=2022)
    s1 = error_scale(bt)
    summ = summarize_backtest(bt, s1)
    inside = sum(r["inside_80"] for r in summ) / sum(r["forecasts"] for r in summ)
    assert 0.65 <= inside <= 0.95          # an 80% range should catch roughly 80% of the test values


def test_forecast_ranges_widen_and_contain_central():
    f = forecast([10, 20, 35, 60, 100], 0.8, 0.16, 5)
    widths = [math.log(r["hi80"] / r["lo80"]) for r in f]
    assert all(b > a for a, b in zip(widths, widths[1:]))
    assert all(r["lo80"] < r["central"] < r["hi80"] and r["slower"] <= r["faster"] for r in f)


def test_locked_forecast_file_is_consistent():
    p = ROOT / "docs" / "data" / "forecast_locked.json"
    if not p.exists():
        return
    import hashlib
    for f in json.loads(p.read_text(encoding="utf-8"))["forecasts"]:
        fp = f.pop("fingerprint")
        assert hashlib.sha256(json.dumps(f, sort_keys=True).encode()).hexdigest()[:16] == fp, "locked forecast was edited"
