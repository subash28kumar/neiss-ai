"""Rebuild the website data from NEISS files.

    python scripts/update_site.py --data-dir data --years 2019-2025 [--download]

Steps: (optionally) download the CPSC annual files, label devices with NEISS-AI, write
docs/data.json (overview), docs/data/records.json and docs/data/stories.json (web app),
and rebuild docs/index.html. Used by the GitHub Actions refresh workflow.
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import neissai  # noqa: E402
from neissai.export import export_web_data  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--data-dir", default="data")
ap.add_argument("--years", default="2019-2025")
ap.add_argument("--download", action="store_true", help="try to download missing files from CPSC first")
a = ap.parse_args()

years = neissai.parse_years(a.years)
if a.download:
    for y in years:
        try:
            neissai.download([y], a.data_dir)
            print(f"downloaded or found neiss{y}")
        except RuntimeError as exc:
            print(f"WARNING: {exc}")
data_dir = Path(a.data_dir)
available = [y for y in years if data_dir.exists() and any(str(y) in p.name for p in data_dir.glob("*neiss*"))]
published = ROOT / "docs" / "data" / "records.json"
required = json.loads(published.read_text())["years"] if published.exists() else []
missing = [y for y in required if y not in available]
if not available or missing:
    # Never publish fewer years than the site already shows (e.g. if a download failed).
    print(f"::warning::Skipping update: missing NEISS files for {missing or years}. "
          "If CPSC changed its download links, update DOWNLOAD_URL in src/neissai/io.py.")
    sys.exit(0)
if max(available) <= max(required or [0]) and published.exists():
    print(f"No new year of data (latest available {max(available)}); site unchanged.")
    sys.exit(0)

df = neissai.read_neiss(a.data_dir, available)
df = neissai.add_outcomes(neissai.label_devices(df))
mm = df["device"].isin(neissai.DEVICES)
by = neissai.national_estimates(df, by=["year", "device"], where=mm)
age = neissai.national_estimates(df, by=["year", "device", "age_group"],
                                 where=mm & df["age_group"].notna() & df["device"].isin(["E-bike", "E-scooter"]))
hosp = neissai.shares(df, "hospitalized", by=["device", "age_group"],
                      where=mm & df["age_group"].notna() & df["device"].isin(["E-bike", "E-scooter", "Bicycle"]))


def rows(d, cols):
    return [{**{c: (int(r[c]) if c == "year" else r[c]) for c in cols}, "est": round(r.estimate), "lo": round(r.ci_low),
             "hi": round(r.ci_high), "n": int(r.records), "unstable": bool(r.unstable)} for _, r in d.iterrows()]


today = dt.date.today().isoformat()
overview = {"updated": today, "source": f"CPSC NEISS annual files {min(available)}-{max(available)}",
            "version": neissai.__version__, "by_device": rows(by, ["year", "device"]),
            "by_age": rows(age, ["year", "device", "age_group"]),
            "hospitalized": [{"device": r.device, "age_group": r.age_group, "share": round(r.share, 4), "lo": round(r.ci_low, 4),
                              "hi": round(r.ci_high, 4), "n": int(r.records)} for _, r in hosp.iterrows()]}
docs = ROOT / "docs"
(docs / "data.json").write_text(json.dumps(overview, indent=1))
info = export_web_data(df, docs / "data", today, neissai.__version__)
html = (docs / "template.html").read_text().replace("/*DATA*/null", (docs / "data.json").read_text())
(docs / "index.html").write_text(html)
print(f"Site data updated for {min(available)}-{max(available)}: {info['records']:,} records.")
