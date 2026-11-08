"""Command line interface.

    neissai download     --years 2019-2025 --data-dir data
    neissai micromobility --years 2019-2025 --data-dir data --out-dir results
    neissai classify "14YOM RIDING ELECTRIC BIKE FELL OFF"
    neissai hazard-export --years 2019-2025 --data-dir data --out-dir neissai_hazard_export
    neissai hazards --export-dir neissai_hazard_export --years 2020-2025 --out-dir hazards
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from . import __version__
from .classifier import EbikeMopedClassifier
from .devices import DEVICES, add_outcomes, label_devices
from .estimate import national_estimates, shares
from .io import download, parse_years, read_neiss


def _fmt(x: float) -> str:
    return f"{x/1000:,.1f}k"


def cmd_download(a: argparse.Namespace) -> int:
    for p in download(a.years, a.data_dir):
        print(f"saved {p}")
    return 0


def cmd_micromobility(a: argparse.Namespace) -> int:
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    print(f"Reading NEISS files for {a.years} from {a.data_dir} ...")
    df = read_neiss(a.data_dir, a.years)
    print(f"  {len(df):,} injury records")
    print("Labelling devices (codes + narratives + text classifier) ...")
    df = add_outcomes(label_devices(df, threshold=a.threshold))
    mm = df["device"].isin(DEVICES)
    print(f"  {int(mm.sum()):,} micromobility records; "
          f"{int((df['label_source'] == 'classifier').sum()):,} labelled by the classifier")

    # Estimates use the full sample design (all records), counting only the selected ones.
    by_year = national_estimates(df, by=["year", "device"], where=mm)
    by_age = national_estimates(df, by=["year", "device", "age_group"], where=mm & df["age_group"].notna())
    sev = pd.concat([shares(df, o, by=["device"], where=mm)
                     for o in ("hospitalized", "head_injury", "motor_vehicle", "helmet_no", "alcohol")])
    df.loc[mm].to_csv(out / "micromobility_records.csv", index=False)
    by_year.to_csv(out / "estimates_by_year_device.csv", index=False)
    by_age.to_csv(out / "estimates_by_year_device_age.csv", index=False)
    sev.to_csv(out / "shares_by_device.csv", index=False)

    tab = by_year.pivot(index="device", columns="year", values="estimate").reindex(DEVICES).dropna(how="all")
    print("\nEstimated US emergency department visits (thousands)")
    print(tab.map(lambda v: "" if pd.isna(v) else _fmt(v)).to_string())
    unstable = by_year[by_year["unstable"]]
    if len(unstable):
        print(f"\n{len(unstable)} estimate(s) are flagged unstable (CPSC rule); see the 'unstable' column.")
    print(f"\nSaved results to {out.resolve()}")
    return 0


def cmd_classify(a: argparse.Namespace) -> int:
    clf = EbikeMopedClassifier.load_default()
    for text in a.text:
        p = float(clf.predict_proba([text])[0])
        print(f"{p:.3f}  {'E-bike' if p >= 0.5 else 'Moped / other power-assisted cycle'}  |  {text}")
    return 0


def cmd_hazards(a: argparse.Namespace) -> int:
    from . import hazards
    data = hazards.read_hazard_export(a.export_dir)
    years = parse_years(a.years)
    counts = hazards.write_scan_outputs(data, a.out_dir, years, cluster=a.cluster)
    print("Emerging-hazard scan: products flagged (excess rise over all-NEISS volume, BH-FDR 5%)")
    for y in years:
        c = counts.get(y, {})
        print(f"  {y}: ED visits {int(c.get('ed_visits', 0))}, admissions {int(c.get('admissions', 0))}"
              + ("  (pandemic year, interpret with caution)" if y in hazards.PANDEMIC_YEARS else ""))
    print(f"Saved results to {Path(a.out_dir).resolve()}")
    return 0


def cmd_hazard_export(a: argparse.Namespace) -> int:
    from . import hazards
    df = read_neiss(a.data_dir, a.years)
    out = hazards.build_hazard_export(df, a.out_dir)
    print(f"Saved clusters.csv, psu.csv and terms.csv for {len(df):,} records to {out.resolve()}")
    print(f"Next: neissai hazards --export-dir {a.out_dir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="neissai", description="AI-assisted national injury estimates from NEISS narratives.")
    ap.add_argument("--version", action="version", version=f"neissai {__version__}")
    sub = ap.add_subparsers(dest="command", required=True)

    d = sub.add_parser("download", help="download CPSC NEISS annual files (best effort)")
    d.add_argument("--years", default="2019-2025")
    d.add_argument("--data-dir", default="data")
    d.set_defaults(func=cmd_download)

    m = sub.add_parser("micromobility", help="e-bike, e-scooter, bicycle and related injury estimates")
    m.add_argument("--years", default="2019-2025")
    m.add_argument("--data-dir", default="data")
    m.add_argument("--out-dir", default="results")
    m.add_argument("--threshold", type=float, default=0.5, help="classifier cut-off for 'E-bike' (default 0.5)")
    m.set_defaults(func=cmd_micromobility)

    c = sub.add_parser("classify", help="e-bike vs moped probability for narrative text")
    c.add_argument("text", nargs="+")
    c.set_defaults(func=cmd_classify)

    e = sub.add_parser("hazard-export", help="make the hazard scan's input tables from downloaded NEISS files")
    e.add_argument("--years", default="2019-2025")
    e.add_argument("--data-dir", default="data")
    e.add_argument("--out-dir", default="neissai_hazard_export")
    e.set_defaults(func=cmd_hazard_export)

    h = sub.add_parser("hazards", help="emerging-hazard scan of every product code (run hazard-export first)")
    h.add_argument("--export-dir", default="neissai_hazard_export",
                   help="folder with clusters.csv, psu.csv and terms.csv")
    h.add_argument("--years", default="2020-2025", help="years to compare with the year before")
    h.add_argument("--out-dir", default="hazards")
    h.add_argument("--cluster", default="hospital", choices=["hospital", "stratum_psu"])
    h.set_defaults(func=cmd_hazards)

    a = ap.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
