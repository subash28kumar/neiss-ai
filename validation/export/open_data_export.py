"""Build the open-data file for Kaggle and Hugging Face: one row per NEISS record that NEISS-AI labels
as a micromobility device (or excludes), with the public NEISS fields and the NEISS-AI labels.

    python validation/export/open_data_export.py --data-dir data [--years 2019-2025]

Writes (in validation/export/):
  neiss_ai_micromobility_2019_2025.csv.gz  the data file
  EXPORT_CHECK.md / export_check.json      row counts by year and device, checked against the
                                           website's docs/data/records.json (must match exactly)
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import neissai  # noqa: E402
from neissai.learn import apply_human_memory  # noqa: E402

OUT = Path(__file__).resolve().parent
NAME = "neiss_ai_micromobility_2019_2025.csv.gz"

COLUMNS = {  # output name: source column
    "cpsc_case_number": "CPSC_Case_Number", "year": "year", "treatment_date": "Treatment_Date",
    "age": "Age", "sex": "Sex", "body_part": "Body_Part", "body_part_2": "Body_Part_2",
    "diagnosis": "Diagnosis", "diagnosis_2": "Diagnosis_2", "disposition": "Disposition",
    "location": "Location", "alcohol": "Alcohol", "drug": "Drug",
    "product_1": "Product_1", "product_2": "Product_2", "product_3": "Product_3",
    "stratum": "Stratum", "psu": "PSU", "weight": "Weight", "narrative": "Narrative",
    "device": "device", "label_source": "label_source", "p_ebike": "p_ebike", "ebike_type": "ebike_type",
    "hospitalized": "hospitalized", "head_injury": "head_injury", "helmet_status": "helmet_status",
    "motor_vehicle": "motor_vehicle",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--years", default="2019-2025")
    a = ap.parse_args()
    years = neissai.parse_years(a.years)

    df = neissai.read_neiss(a.data_dir, years)
    df = neissai.add_outcomes(neissai.label_devices(df))
    df = neissai.add_ebike_type(df)
    df = apply_human_memory(df)
    keep = df["label_source"].astype(str) != ""  # every record the rules or the classifier labelled
    out = df.loc[keep, list(COLUMNS.values())].rename(columns={v: k for k, v in COLUMNS.items()})
    out.loc[out["device"] != "E-bike", "ebike_type"] = ""
    out["p_ebike"] = out["p_ebike"].round(4)
    out["age"] = out["age"].round(2)
    out["neissai_version"] = neissai.__version__
    out = out.sort_values(["year", "cpsc_case_number"]).reset_index(drop=True)
    out.to_csv(OUT / NAME, index=False, compression={"method": "gzip", "mtime": 0})

    # Check: device counts must equal the website's records.json exactly.
    rec = json.loads((ROOT / "docs" / "data" / "records.json").read_text())
    site = Counter((rec["years"][y], rec["devices"][d]) for y, d in zip(rec["y"], rec["d"]))
    mine = Counter((int(y), d) for y, d in zip(out["year"], out["device"]) if d in neissai.DEVICES)
    keys = sorted(set(site) | set(mine))
    diffs = [(k, site.get(k, 0), mine.get(k, 0)) for k in keys if site.get(k, 0) != mine.get(k, 0)]
    by_dev = Counter(out["device"])
    check = {"version": neissai.__version__, "site_version": rec.get("version"), "rows": int(len(out)),
             "micromobility_rows": int(sum(mine.values())), "site_rows": int(rec["n"]),
             "by_device": dict(sorted(by_dev.items())), "mismatches": [[k[0], k[1], s, m] for k, s, m in diffs],
             "match": not diffs, "unique_case_numbers": int(out["cpsc_case_number"].nunique())}
    (OUT / "export_check.json").write_text(json.dumps(check, indent=1))
    lines = [f"# Open-data export check (NEISS-AI {neissai.__version__})", "",
             f"Rows written: {len(out):,} ({check['micromobility_rows']:,} micromobility; rest = Excluded).",
             f"Website records.json rows: {rec['n']:,} (site version {rec.get('version')}).",
             f"Device counts by year match the website exactly: **{'YES' if not diffs else 'NO'}**", "",
             "| Device | Rows |", "|---|---|"] + [f"| {k} | {v:,} |" for k, v in sorted(by_dev.items())]
    if diffs:
        lines += ["", "Mismatches (year, device, website, export):"] + [f"- {k[0]} {k[1]}: {s} vs {m}" for k, s, m in diffs]
    (OUT / "EXPORT_CHECK.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
