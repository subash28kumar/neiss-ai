"""Reading NEISS annual data files.

The US Consumer Product Safety Commission (CPSC) publishes one file per year
(for example ``neiss2025.tsv``) at https://www.cpsc.gov/Research--Statistics/NEISS-Injury-Data.
Column names have changed slightly over the years; ``read_neiss`` returns the same
column names for every year.
"""
from __future__ import annotations

import re
import urllib.request
from pathlib import Path
from typing import Iterable, Optional, Sequence, Union

import pandas as pd

PathLike = Union[str, Path]

#: Best-effort download location for the annual files. CPSC may change it; if a
#: download fails, download the files by hand from the NEISS page and use --data-dir.
DOWNLOAD_URL = "https://www.cpsc.gov/cgi-bin/NEISSQuery/Data/Archived%20Data/{year}/neiss{year}.tsv"

STANDARD_COLUMNS = [
    "CPSC_Case_Number", "Treatment_Date", "Age", "Sex", "Body_Part", "Diagnosis",
    "Body_Part_2", "Diagnosis_2", "Disposition", "Location", "Fire_Involvement",
    "Product_1", "Product_2", "Product_3", "Alcohol", "Drug", "Narrative",
    "Stratum", "PSU", "Weight", "year",
]

_RENAME = {
    "narrative_1": "Narrative", "narrative": "Narrative", "narr": "Narrative",
    "cpsc_case_number": "CPSC_Case_Number", "cpsc_case_no": "CPSC_Case_Number",
    "treatment_date": "Treatment_Date", "trmt_date": "Treatment_Date",
    "body_part": "Body_Part", "body_part_2": "Body_Part_2",
    "diagnosis": "Diagnosis", "diagnosis_2": "Diagnosis_2", "diag": "Diagnosis", "diag_2": "Diagnosis_2",
    "product_1": "Product_1", "product_2": "Product_2", "product_3": "Product_3",
    "prod1": "Product_1", "prod2": "Product_2", "prod3": "Product_3",
    "fire_involvement": "Fire_Involvement", "fmv": "Fire_Involvement",
    "age": "Age", "sex": "Sex", "disposition": "Disposition", "location": "Location",
    "alcohol": "Alcohol", "drug": "Drug", "stratum": "Stratum", "psu": "PSU", "weight": "Weight",
}


def parse_years(spec: Union[str, int, Iterable[int]]) -> list[int]:
    """Turn '2019-2025', '2023,2025' or 2024 into a list of years."""
    if isinstance(spec, int):
        return [spec]
    if not isinstance(spec, str):
        return sorted(int(y) for y in spec)
    years: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = (int(x) for x in part.split("-"))
            years.update(range(a, b + 1))
        elif part:
            years.add(int(part))
    return sorted(years)


def standardize(df: pd.DataFrame, year: Optional[int] = None) -> pd.DataFrame:
    """Give a raw NEISS table the standard column names and types."""
    df = df.copy()
    df.columns = [re.sub(r"^﻿|ï»¿", "", str(c)).strip() for c in df.columns]
    df = df.rename(columns={c: _RENAME.get(c.lower(), c) for c in df.columns})
    for col in STANDARD_COLUMNS:
        if col not in df.columns and col != "year":
            df[col] = pd.NA
    for col in ("Product_1", "Product_2", "Product_3", "Body_Part", "Body_Part_2",
                "Disposition", "Alcohol", "Drug", "Sex", "Diagnosis", "Diagnosis_2"):
        df[col] = (df[col].astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
                   .fillna("0"))
    df["Narrative"] = df["Narrative"].astype("string").fillna("")
    df["Weight"] = pd.to_numeric(df["Weight"], errors="coerce")
    df["Stratum"] = df["Stratum"].astype("string").str.strip()
    df["PSU"] = df["PSU"].astype("string").str.strip()
    age = pd.to_numeric(df["Age"], errors="coerce").astype(float)
    infants = age > 200  # NEISS codes ages under 2 as 200 + months
    age[infants] = (age[infants] - 200) / 12
    df["Age"] = age
    if year is not None:
        df["year"] = int(year)
    elif "file_year" in df.columns:
        df["year"] = pd.to_numeric(df["file_year"], errors="coerce").astype("Int64")
    else:
        df["year"] = pd.to_datetime(df["Treatment_Date"], errors="coerce").dt.year.astype("Int64")
    return df


def read_neiss_file(path: PathLike, year: Optional[int] = None) -> pd.DataFrame:
    """Read one NEISS file (.tsv, .txt, .csv or .xlsx)."""
    path = Path(path)
    if year is None:
        m = re.search(r"(19|20)\d{2}", path.name)
        year = int(m.group(0)) if m else None
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        raw = pd.read_excel(path, dtype=str)
    else:
        sep = "," if suffix == ".csv" else "\t"
        raw = pd.read_csv(path, sep=sep, dtype=str, encoding="latin-1", low_memory=False)
    return standardize(raw, year)


def read_neiss(data_dir: PathLike, years: Union[str, Sequence[int]] = "2019-2025") -> pd.DataFrame:
    """Read the NEISS files for the given years from one folder.

    Files are matched by name, e.g. ``neiss2024.tsv`` or ``NEISS_2024.xlsx``.
    """
    data_dir = Path(data_dir)
    frames = []
    missing = []
    for year in parse_years(years):
        hits = sorted(p for p in data_dir.iterdir()
                      if p.is_file() and str(year) in p.name and "neiss" in p.name.lower()
                      and p.suffix.lower() in (".tsv", ".txt", ".csv", ".xlsx", ".xls"))
        if not hits:
            missing.append(year)
            continue
        frames.append(read_neiss_file(hits[0], year))
    if missing:
        raise FileNotFoundError(
            f"No NEISS file found in {data_dir} for: {', '.join(map(str, missing))}. "
            "Download the annual files from https://www.cpsc.gov/Research--Statistics/NEISS-Injury-Data "
            "or run `neissai download`.")
    return pd.concat(frames, ignore_index=True)


def download(years: Union[str, Sequence[int]], data_dir: PathLike, url_template: str = DOWNLOAD_URL) -> list[Path]:
    """Try to download NEISS annual files into ``data_dir``.

    CPSC's file locations can change. If this fails, download the files by hand.
    """
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for year in parse_years(years):
        target = data_dir / f"neiss{year}.tsv"
        if target.exists():
            saved.append(target)
            continue
        url = url_template.format(year=year)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "neissai (https://github.com/subash28kumar/neiss-ai)"})
            with urllib.request.urlopen(req, timeout=120) as r, open(target, "wb") as f:
                f.write(r.read())
            saved.append(target)
        except Exception as exc:  # pragma: no cover - network dependent
            if target.exists():
                target.unlink()
            raise RuntimeError(
                f"Could not download {url} ({exc}). Please download neiss{year}.tsv by hand from "
                "https://www.cpsc.gov/Research--Statistics/NEISS-Injury-Data") from exc
    return saved
