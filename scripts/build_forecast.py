"""Build docs/data/forecast.json (forecasts 1-5 years ahead, back-test, forecast-vs-actual checks).

Also LOCKS the first forecast for each new year in docs/data/forecast_locked.json: once a year's
forecast is written there it is never changed, so it can be checked in public when CPSC releases
that year's data. Run after docs/data.json is rebuilt (scripts/update_site.py calls this).

Run: PYTHONPATH=src python scripts/build_forecast.py
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from neissai.forecast import (BACKTEST_DEVICES, backtest, choose_phi, error_scale, forecast, series,
                              summarize_backtest)

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DEVICES = ("E-bike", "E-scooter", "Kick scooter", "Bicycle")
HORIZON = 5
TESTED_YEARS = 3   # the back-test can check forecasts up to 3 years ahead


def main() -> None:
    data = json.loads((DOCS / "data.json").read_text(encoding="utf-8"))
    bd = data["by_device"]
    last = max(r["year"] for r in bd)
    first_cut = last - TESTED_YEARS
    pick = choose_phi(bd, first_cut=first_cut)
    phi = pick["phi"]
    bt = backtest(bd, phi, first_cut=first_cut)
    sigma1 = error_scale(bt)
    summary = summarize_backtest(bt, sigma1)

    out = {
        "updated": data.get("updated") or date.today().isoformat(),
        "version": data.get("version"),
        "last_data_year": last,
        "method": {
            "name": "Slowing growth (damped trend on the log scale)",
            "phi": phi, "slower_phi": 0.6, "faster_phi": 0.95, "window_years": 3, "sigma_1yr": sigma1,
            "phi_scores": {str(k): v for k, v in pick["scores"].items()}, "best_phi": pick["best_phi"],
            "one_se_limit": pick["limit"],
            "backtest_devices": list(BACKTEST_DEVICES),
            "tested_years_ahead": TESTED_YEARS,
            "text": ("Next year's growth is the average yearly growth of the last 3 years multiplied by "
                     f"{phi}; each later year multiplies by {phi} again, so growth slows over time. "
                     f"The slowing factor was chosen (one-standard-error rule, the most cautious value that tests about as "
                     f"well as the best) by testing forecasts made from data up to "
                     f"{first_cut}, {first_cut + 1} and {first_cut + 2} against what NEISS later showed, for "
                     f"{len(BACKTEST_DEVICES)} devices. The 80% ranges come from the size of those test misses."),
        },
        "backtest": {"summary": summary,
                     "detail": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()} for r in bt]},
        "devices": {},
    }
    for dev in DEVICES:
        s = series(bd, dev)
        years = sorted(s)
        hist = [s[y] for y in years]
        nat = {r["year"]: r for r in bd if r["device"] == dev}
        fc = forecast(hist, phi, sigma1, HORIZON)
        out["devices"][dev] = {
            "actual": [{"year": y, "est": nat[y]["est"], "lo": nat[y]["lo"], "hi": nat[y]["hi"],
                        "unstable": nat[y]["unstable"]} for y in years],
            "forecast": [{"year": last + r["h"], "tested": r["h"] <= TESTED_YEARS,
                          **{k: int(round(r[k])) for k in ("central", "lo80", "hi80", "slower", "faster")}}
                         for r in fc],
        }

    # e-bike visits as a share of bicycle visits (central path)
    eb, bi = out["devices"]["E-bike"], out["devices"]["Bicycle"]
    out["ebike_vs_bicycle"] = (
        [{"year": a["year"], "share": a["est"] / b["est"], "kind": "actual"} for a, b in zip(eb["actual"], bi["actual"])]
        + [{"year": a["year"], "share": a["central"] / b["central"], "kind": "forecast"}
           for a, b in zip(eb["forecast"], bi["forecast"])])

    # lock next year's forecast the first time it is made; never overwrite
    lock_path = DOCS / "data" / "forecast_locked.json"
    locked = json.loads(lock_path.read_text(encoding="utf-8")) if lock_path.exists() else {"forecasts": []}
    target = last + 1
    if not any(f["year"] == target for f in locked["forecasts"]):
        entry = {"year": target, "locked_on": date.today().isoformat(), "made_with_data_through": last,
                 "version": data.get("version"), "phi": phi, "sigma_1yr": round(sigma1, 4),
                 "devices": {d: {k: out["devices"][d]["forecast"][0][k] for k in ("central", "lo80", "hi80")}
                             for d in DEVICES}}
        entry["fingerprint"] = hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()[:16]
        locked["forecasts"].append(entry)
        lock_path.write_text(json.dumps(locked, indent=1), encoding="utf-8")
        print(f"locked forecast for {target} (fingerprint {entry['fingerprint']})")
    # forecast vs actual, for every locked year that now has data
    checks = []
    for f in locked["forecasts"]:
        if f["year"] <= last:
            for d, v in f["devices"].items():
                a = next((r for r in out["devices"].get(d, {}).get("actual", []) if r["year"] == f["year"]), None)
                if a:
                    checks.append({"year": f["year"], "device": d, "forecast": v["central"], "lo80": v["lo80"],
                                   "hi80": v["hi80"], "actual": a["est"], "inside_80": v["lo80"] <= a["est"] <= v["hi80"],
                                   "miss": a["est"] / v["central"] - 1, "locked_on": f["locked_on"]})
    out["locked"] = locked["forecasts"]
    out["checks"] = checks

    path = DOCS / "data" / "forecast.json"
    path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    e1 = eb["forecast"][0]
    print(f"wrote {path}: phi={phi}, sigma1={sigma1:.3f}; E-bike {last + 1}: {e1['central']:,} "
          f"(80% {e1['lo80']:,}-{e1['hi80']:,})")
    for r in summary:
        print(f"  {r['years_ahead']} yr ahead: {r['forecasts']} tests, median miss {r['median_miss']:.0%}, "
              f"inside 80% range {r['inside_80']}/{r['forecasts']}")


if __name__ == "__main__":
    main()
