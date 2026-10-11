"""Export labelled micromobility records in a compact form for the web app (docs/).

The web app computes national estimates in the browser, so it needs record-level data:
year, device, age, sex, body part, diagnosis, disposition, flags, sample design (stratum,
hospital) and weight. Narratives go to a separate file that is loaded only for story search.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd

from .devices import DEVICES

FLAG_BITS = {"helmet_no": 1, "helmet_yes": 2, "motor_vehicle": 4, "alcohol": 8, "fire": 16, "drug": 32}


def _int(s: pd.Series) -> list[int]:
    return pd.to_numeric(s, errors="coerce").fillna(0).astype(int).tolist()


def export_web_data(labeled: pd.DataFrame, out_dir: Union[str, Path], updated: str, version: str) -> dict:
    """Write ``records.json`` and ``stories.json`` for the web app. Returns summary info."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    d = labeled[labeled["device"].isin(DEVICES)].copy()
    d = d[d["year"].notna() & d["Weight"].notna()].reset_index(drop=True)
    years = sorted(int(y) for y in d["year"].unique())
    strata = sorted(d["Stratum"].astype(str).unique())
    d["cluster"] = d["Stratum"].astype(str) + "_" + d["PSU"].astype(str)
    clusters = sorted(d["cluster"].unique())
    cl_index = {c: i for i, c in enumerate(clusters)}
    st_index = {s: i for i, s in enumerate(strata)}

    flags = np.zeros(len(d), dtype=int)
    fire = pd.to_numeric(d.get("Fire_Involvement", 0), errors="coerce").fillna(0).astype(int).isin([1, 2, 3])
    drug = d.get("Drug", pd.Series("0", index=d.index)).astype(str) == "1"
    for col, bit in FLAG_BITS.items():
        if col == "fire":
            flags |= fire.to_numpy().astype(int) * bit
        elif col == "drug":
            flags |= drug.to_numpy().astype(int) * bit
        else:
            flags |= d[col].fillna(0).astype(int).to_numpy() * bit

    age = d["Age"].fillna(-1)
    records = {
        "years": years,
        "devices": DEVICES,
        "strata": strata,
        "cluster_stratum": [st_index[c.split("_")[0]] for c in clusters],
        "n": int(len(d)),
        "y": [years.index(int(v)) for v in d["year"]],
        "d": [DEVICES.index(v) for v in d["device"]],
        "a": [int(np.floor(v)) if v >= 0 else -1 for v in age],
        "s": _int(d["Sex"]),
        "b": _int(d["Body_Part"]),
        "b2": _int(d["Body_Part_2"]),
        "g": _int(d["Diagnosis"]),
        "g2": _int(d["Diagnosis_2"]),
        "p": _int(d["Disposition"]),
        "f": flags.tolist(),
        "c": [cl_index[c] for c in d["cluster"]],
        "w": [round(float(v), 4) for v in d["Weight"]],
        "flag_bits": FLAG_BITS,
        "updated": updated,
        "version": version,
        "source": "US CPSC NEISS annual data files",
    }
    (out / "records.json").write_text(json.dumps(records, separators=(",", ":")))
    stories = d["Narrative"].astype(str).str.upper().str.replace(r"\s+", " ", regex=True).str.strip().tolist()
    (out / "stories.json").write_text(json.dumps(stories, separators=(",", ":")))
    return {"records": len(d), "years": years, "clusters": len(clusters)}
