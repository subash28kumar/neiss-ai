"""Emerging-hazard scan: which products rose more than all of NEISS did?

For every product code the scan compares one period (a year, or some months of a year)
with the same months of the year before, separately for emergency department (ED) visits
and for hospital admissions, and asks: did this product rise by more than the whole NEISS
sample rose? That "excess change" matters because NEISS weights can jump for every
product at once (in 2024 the all-NEISS weighted total rose about 18%).

Statistics, kept in the same style as :mod:`neissai.estimate`:

* National totals are summed weights; standard errors use Taylor linearization with
  hospitals (PSUs) as clusters within strata. Hospitals with no records for a product
  count as zeros (taken from the list of participating hospitals), so a single-year total
  and SE equal :func:`neissai.total` on the full NEISS file.
* The excess change is ``Y_now - Y_before * T_now / T_before`` (``T`` = all-NEISS total for
  the same measure). Its SE uses the linearized variable for every hospital, so the
  correlation between the two years and with the all-NEISS total is included.
* One-sided test for a rise, Benjamini-Hochberg false discovery rate across products,
  minimum detectable change (MDC) at 80% power, and CPSC's reporting rule (unstable if
  fewer than 20 records, an estimate below 1,200 or a CV above 33%).
* CPSC product-code changes: the known code groups (e-bikes 3215 -> 5045/5046 in 2024,
  scooters 1329/5042 -> 5022-5025 in 2020, cribs 1543/1545 -> 1552 in 2021) are used ONLY
  when the codes change between the two compared periods. Any other code that starts or
  stops between the periods is detected automatically and is not flagged.

Input: three small tables made from the full CPSC NEISS files (``clusters.csv``, ``psu.csv``,
``terms.csv``): build them with :func:`build_hazard_export` (or ``neissai hazard-export``) and
read them with :func:`read_hazard_export`.
"""
from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from statistics import NormalDist
from typing import Iterable, Optional, Sequence, Union

import numpy as np
import pandas as pd

from .estimate import _unstable

PathLike = Union[str, Path]

#: Product code the export uses for "all NEISS records" (every record counted once).
ALL_PRODUCTS = "0"

#: Measures: name -> (records column, weight column)
MEASURES = {"ed_visits": ("n", "w"), "admissions": ("n_hosp", "w_hosp")}

PANDEMIC_YEARS = (2020, 2021)
PANDEMIC_NOTE = "pandemic years, interpret with caution"
PANDEMIC_BASE_NOTE = "prior year is a pandemic year, interpret with caution"
WEIGHTS_2024_NOTE = ("NEISS weights rose ~18% in 2024 (strata S +27%, V +46%); "
                     "large minimum detectable changes, see methods note")


@dataclass(frozen=True)
class CodeGroup:
    name: str
    codes: tuple
    changed_in: int
    note: str = ""

    @property
    def id(self) -> str:
        return "+".join(self.codes)


#: CPSC code changes in 2019-2025. Used only when the codes change between compared periods.
CODE_GROUPS = (
    CodeGroup("E-bikes, mopeds and power-assisted cycles", ("3215", "5045", "5046"), 2024,
              "CPSC split 3215 into 5045 (e-bikes) and 5046 in 2024"),
    CodeGroup("Scooters and hoverboards", ("1329", "5042", "5022", "5023", "5024", "5025"), 2020,
              "CPSC replaced 1329/5042 with 5022-5025 in 2020"),
    CodeGroup("Cribs", ("1543", "1545", "1552"), 2021, "CPSC replaced 1543/1545 with 1552 in 2021"),
)

#: Product names: CPSC NEISS product code labels (format file), tidied; e-mobility and other
#: flagged codes were written out in full by NEISS-AI. Stored in ``model/product_codes.csv``.
def _load_product_names() -> dict:
    path = Path(__file__).with_name("model") / "product_codes.csv"
    try:
        t = pd.read_csv(path, dtype={"code": str})
    except FileNotFoundError:  # pragma: no cover - package data missing
        return {}
    return dict(zip(t["code"].str.strip(), t["name"].astype(str)))


PRODUCT_NAMES = _load_product_names()
for _g in CODE_GROUPS:
    PRODUCT_NAMES[_g.id] = f"{_g.name} (CPSC code group)"

#: Coding-practice questions still open (shown in the ``note`` column).
PENDING_CHECKS = {
    ("1807", 2025): "large 2025 jump, likely coding practice; label pending check",
}

# --- writing-style filter for narrative terms -------------------------------------------
#: Charting habits and abbreviations that change with who writes the story, not with hazards.
STYLE_WORDS = frozenset("""
PT PTS PT'S PATIENT PATIENTS PATIENT'S YOM YOF YO Y/O YOA YR YRS YEAR YEARS OLD MO MOS MONTH MONTHS
MALE FEMALE M F DX DXD DIAGNOSIS DIAGNOSED IMPRESSION CC C/O CO COMPLAINS COMPLAINING COMPLAINT
COMPLAINTS STATES STATED STATE STATING SAYS SAID REPORTS REPORTED REPORTING REPORTEDLY REPORT PER
PRESENTS PRESENTED PRESENTING PRESENTATION ARRIVES ARRIVED ARRIVAL BIB BIBEMS BIBA EMS ED ER
TRIAGE HX HISTORY PMH PMHX S/P SP NS NOS UNSPECIFIED UNSPEC INITIAL INTIAL ENCOUNTER SUBSEQUENT
EXAM EXAMINATION NOTES NOTE NOTED EVAL EVALUATION EVALUATED CHART SCANS SCAN NEGATIVE POSITIVE
TODAY TONIGHT YESTERDAY AGO HRS HR HOURS DAYS DAY WEEK WEEKS PTA PRIOR APPROX APPROXIMATELY
COMING COMES CAME BROUGHT SUFFERED SUSTAINED SUSTAINING EXPERIENCED EXPERIENCING ENDORSES DENIES
ACCIDENTALLY ACCIDENTAL ALLEGEDLY POSSIBLE POSSIBLY LIKELY SUSPECTED ACUTE CHRONIC
SEEN LWOT LWBS LBFE LWBE AMA ELOPED DISCHARGED PROVIDED DETAILS INFORMATION OBTAINED RESULTING
RESULTED OCCURRED OCCURRING FOLLOWING EVENT EMERGENCY DEPARTMENT PRESENT PRESNETED PRESNTS STS
TAKES OVERT POV RADIOGRAPHS IMAGING XRAY XRAYS CT MRI NLOC FWD ENDORSED ENDORSING PROBLEM INJ BDY
GLF UDS TRAUMA ALERT VERSUS VS SHOWS SHOWED REVEALS REVEALED UNKNOWN UNK CHIEF SITE WORSENING
EARLIER MINUTES MIN REMARKABLE UNREMARKABLE STR STATUS POST DEVELOP DEVELOPED GRADUALLY SUDDEN
SUDDENLY CONTINUED CONTINUES LOCAL DOES DID TREATMENT COMPLETE SERVICES INITAL EXTERMITY
EXTREMITY EXTREMITIES EXTERNAL TRAUMATIC IMPACTING APPARENTLY HAVING ABLE UNABLE CONT ALTERED
SIGN SIGNS SYMPTOMS HEADSTRIKE STRIKE CONFIRMED DESCRIBED DESCRIBES PRIOR AFTERWARDS LATER
""".split())
#: Clinical and body words (laterality, diagnoses, body parts): not a product or a hazard by themselves.
CLINICAL_WORDS = frozenset("""
LEFT RIGHT LT RT BILATERAL L R PAIN PAINFUL INJURY INJURIES INJURED CONTUSION CONTUSIONS ABRASION
ABRASIONS LACERATION LACERATIONS LAC FRACTURE FRACTURES FX STRAIN SPRAIN STRAINED SPRAINED
DISLOCATION AVULSION PUNCTURE HEMATOMA BRUISE BRUISING SWELLING BURN BURNS CHI HEAD FACE FACIAL
SCALP NECK BACK LOWER UPPER CHEST ABD ABDOMEN ABDOMINAL SHOULDER ARM ELBOW WRIST HAND FINGER FINGERS
THUMB HIP KNEE LEG ANKLE FOOT FEET TOE TOES EYE EYES EAR NOSE MOUTH LIP TOOTH TEETH BODY TRUNK
LOC CONSCIOUS CONSCIOUSNESS LOSS CLOSED OPEN MINOR MILD SEVERE DIZZINESS SYNCOPE CONCUSSION
BLOOD THINNERS THINNER ANTICOAGULANT ETOH BAC INTOXICATED ALCOHOL C-H-I
FALL FELL FALLING GROUND LEVEL MECHANICAL TRIPPED SLIPPED STRUCK STRIKING HITTING HIT
TENDERNESS MYALGIA DIZZY WEAKNESS HEADACHE VOMITING NAUSEA HYPERTENSION DEMENTIA DEMENTED
FRACTURED DISPLACED NONDISPLACED DISTAL PROXIMAL SHAFT RADIUS ULNA RIB RIBS VERTEBRA MULTIPLE
""".split())
#: Places, people and time words: context, not a product or a hazard by themselves.
CONTEXT_WORDS = frozenset("""
HOME HOUSE INSIDE OUTSIDE BATHROOM BEDROOM KITCHEN NURSING FACILITY SCHOOL WORK AMBULANCE
MOTHER FATHER MOM DAD CHILD SON DAUGHTER SIBLING BROTHER SISTER FRIEND PEDIATRIC WALK AWAY
""".split())
_STYLE_PATTERNS = (re.compile(r"\d"), re.compile(r"^[A-Z]$"), re.compile(r"^[^A-Z]+$"))

_ND = NormalDist()


# --- loading ------------------------------------------------------------------------------
def read_hazard_export(folder: PathLike) -> dict:
    """Read ``clusters.csv``, ``psu.csv`` and ``terms.csv`` from the Colab export folder.

    * clusters: product, year, month, Stratum, PSU, n, w, n_hosp, w_hosp
      (one row per product x year x month x hospital; product ``"0"`` = all records)
    * psu: year, Stratum, PSU (every participating hospital, needed for zero cells)
    * terms: term, year, n, w (narrative word and two-word counts, n >= 10)
    """
    folder = Path(folder)
    clusters = pd.read_csv(folder / "clusters.csv", dtype={"product": str, "Stratum": str, "PSU": str},
                           keep_default_na=False, na_values=[""])
    psu = pd.read_csv(folder / "psu.csv", dtype=str)
    psu["year"] = psu["year"].astype(int)
    for col in ("Stratum", "PSU"):  # a few records have no stratum/hospital (weight 0)
        psu[col] = psu[col].astype("string").str.strip().fillna("NA").astype(str)
    out = {"clusters": _clean_clusters(clusters), "psu": psu}
    if (folder / "terms.csv").exists():
        terms = pd.read_csv(folder / "terms.csv", dtype={"term": str}, keep_default_na=False,
                            na_values={"n": [""], "w": [""]})
        terms["n"] = pd.to_numeric(terms["n"])
        terms["w"] = pd.to_numeric(terms["w"])
        out["terms"] = terms
    return out


def _clean_clusters(c: pd.DataFrame) -> pd.DataFrame:
    c = c.copy()
    c["product"] = c["product"].astype(str).str.strip()
    for col in ("Stratum", "PSU"):
        c[col] = c[col].astype("string").str.strip().fillna("NA").astype(str)
    for col in ("n", "n_hosp"):
        c[col] = pd.to_numeric(c[col]).astype(int)
    for col in ("w", "w_hosp"):
        c[col] = pd.to_numeric(c[col]).astype(float)
    return c


def clusters_from_records(df: pd.DataFrame, hospitalized: str = "hospitalized") -> tuple:
    """Build ``(clusters, psu)`` tables from a standardized NEISS record table.

    Mirrors the Colab export: each record counts once under each distinct product code in
    Product_1..3, and once under ``"0"`` (all records). Useful for tests and small extracts.
    """
    d = df.copy()
    d["month"] = pd.to_datetime(d["Treatment_Date"], errors="coerce").dt.month.fillna(0).astype(int)
    d["_hosp"] = d[hospitalized].astype(int) if hospitalized in d else 0
    d["_rid"] = np.arange(len(d))
    long = (d.melt(id_vars=["_rid", "year", "month", "Stratum", "PSU", "Weight", "_hosp"],
                   value_vars=["Product_1", "Product_2", "Product_3"], value_name="product")
            .query("product != '0'").drop_duplicates(["_rid", "product"]))
    allrec = d.assign(product=ALL_PRODUCTS)
    long = pd.concat([long, allrec[long.columns.intersection(allrec.columns)]], ignore_index=True)
    long["w_h"] = long["Weight"] * long["_hosp"]
    c = (long.groupby(["product", "year", "month", "Stratum", "PSU"], dropna=False)
         .agg(n=("Weight", "size"), w=("Weight", "sum"), n_hosp=("_hosp", "sum"), w_hosp=("w_h", "sum"))
         .reset_index())
    psu = d[["year", "Stratum", "PSU"]].dropna().drop_duplicates().astype({"year": int})
    return _clean_clusters(c), psu.astype({"Stratum": str, "PSU": str}).reset_index(drop=True)


#: Short English words dropped before counting words and word pairs in the injury stories.
TERM_STOPWORDS = frozenset("""
A AN THE AND OR BUT OF TO IN ON AT BY FOR FROM WITH WITHOUT INTO ONTO OFF UP DOWN OUT OVER UNDER
AS IS WAS WERE BE BEEN BEING ARE AM HE SHE IT HIS HER HIM HERS ITS THEY THEM THEIR THIS THAT THESE
THOSE THERE THEN THAN WHILE WHEN WHERE WHICH WHO WHOM WHAT AFTER BEFORE DURING ALSO NOT NO SO IF
HAS HAD HAVE WILL WOULD CAN COULD SHOULD MAY MIGHT ANOTHER SOME ANY ALL EACH ABOUT AGAINST BETWEEN
THROUGH WITHIN ALONG AROUND ONE TWO
""".split())
_TOKEN = re.compile(r"[A-Z][A-Z'/-]*[A-Z]|[A-Z]")


def narrative_terms(text: str) -> set:
    """Distinct words and adjacent word pairs in one injury story, upper case, after dropping
    :data:`TERM_STOPWORDS` (so 'fell to the floor' gives FELL, FLOOR and FELL FLOOR)."""
    words = [w for w in _TOKEN.findall(str(text).upper()) if w not in TERM_STOPWORDS]
    return set(words) | {f"{a} {b}" for a, b in zip(words, words[1:])}


def term_counts(df: pd.DataFrame, min_count: int = 10) -> pd.DataFrame:
    """Per year: number of stories (``n``) and summed weights (``w``) that contain each term;
    terms used in fewer than ``min_count`` stories that year are dropped."""
    rows = []
    for year, g in df.groupby("year"):
        n: dict = {}
        w: dict = {}
        for text, weight in zip(g["Narrative"].astype(str), pd.to_numeric(g["Weight"], errors="coerce").fillna(0)):
            for t in narrative_terms(text):
                n[t] = n.get(t, 0) + 1
                w[t] = w.get(t, 0.0) + float(weight)
        rows.append(pd.DataFrame({"term": list(n), "year": int(year), "n": list(n.values()),
                                  "w": [w[t] for t in n]}))
    out = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["term", "year", "n", "w"])
    return out[out["n"] >= min_count].sort_values(["term", "year"]).reset_index(drop=True)


def build_hazard_export(df: pd.DataFrame, out_dir: PathLike, min_term_count: int = 10) -> Path:
    """Make the scan's input tables (``clusters.csv``, ``psu.csv``, ``terms.csv``) from NEISS
    records read with :func:`neissai.io.read_neiss`. Admissions are dispositions 2, 4, 5 or 8
    (transferred, admitted, held for observation, died), as in :mod:`neissai.devices`.
    The published 2019-2025 tables were made the same way in Colab; word counts can differ
    slightly from them because the original word list rules were not saved."""
    d = df.copy()
    disp = d["Disposition"].astype("string").str.extract(r"^\s*(\d)")[0]
    d["hospitalized"] = disp.isin(["2", "4", "5", "8"]).astype(int)
    for col in ("Product_1", "Product_2", "Product_3"):
        d[col] = d[col].astype("string").fillna("0").str.strip()
    d["year"] = d["year"].astype(int)
    clusters, psu = clusters_from_records(d, hospitalized="hospitalized")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    clusters.to_csv(out / "clusters.csv", index=False)
    psu.to_csv(out / "psu.csv", index=False)
    term_counts(d, min_term_count).to_csv(out / "terms.csv", index=False)
    return out


# --- design helpers -----------------------------------------------------------------------
def _select(c: pd.DataFrame, year: int, months: Optional[Sequence[int]]) -> pd.DataFrame:
    s = c[c["year"] == year]
    return s if months is None else s[s["month"].isin(list(months))]


def _strat_var(Z: np.ndarray, strata: np.ndarray) -> np.ndarray:
    """Row-wise with-replacement variance of cluster totals, summed over strata (as estimate.py)."""
    var = np.zeros(Z.shape[0])
    for s in np.unique(strata):
        cols = strata == s
        n = int(cols.sum())
        if n > 1:
            Zs = Z[:, cols]
            var += n / (n - 1) * ((Zs - Zs.mean(axis=1, keepdims=True)) ** 2).sum(axis=1)
    return var


def _design(psu: pd.DataFrame, years: Sequence[int], cluster: str) -> pd.DataFrame:
    """Hospitals (cluster id, stratum) for one year or a pair of years.

    ``cluster="hospital"``: a hospital is matched across the two years by its PSU number and
    placed in its stratum in the later year (CPSC redrew strata in 2024).
    ``cluster="stratum_psu"``: each (stratum, PSU) is its own cluster, so a hospital that moved
    stratum counts as two independent clusters.
    """
    p = psu[psu["year"].isin(list(years))].copy()
    p["Stratum"] = p["Stratum"].astype(str)
    p["PSU"] = p["PSU"].astype(str)
    if cluster == "hospital":
        p = p.sort_values("year").drop_duplicates("PSU", keep="last")
        d = pd.DataFrame({"cid": p["PSU"].values, "stratum": p["Stratum"].values})
    elif cluster == "stratum_psu":
        p = p.drop_duplicates(["Stratum", "PSU"])
        d = pd.DataFrame({"cid": (p["Stratum"] + ":" + p["PSU"]).values, "stratum": p["Stratum"].values})
    else:
        raise ValueError("cluster must be 'hospital' or 'stratum_psu'")
    # records with no stratum/hospital (weight 0 in the export) form their own one-cluster stratum
    na = pd.DataFrame({"cid": ["NA" if cluster == "hospital" else "NA:NA"], "stratum": ["NA"]})
    return pd.concat([d, na], ignore_index=True).drop_duplicates("cid").reset_index(drop=True)


def _cid(sub: pd.DataFrame, cluster: str) -> pd.Series:
    return sub["PSU"] if cluster == "hospital" else sub["Stratum"] + ":" + sub["PSU"]


def _matrix(sub: pd.DataFrame, design: pd.DataFrame, products: pd.Index, value: str,
            cluster: str) -> np.ndarray:
    """products x hospitals matrix of summed ``value`` (zeros where a hospital has no records)."""
    g = sub.assign(cid=_cid(sub, cluster)).groupby(["product", "cid"])[value].sum()
    unknown = set(g.index.get_level_values("cid")) - set(design["cid"])
    if unknown:
        raise ValueError(f"hospitals missing from psu.csv: {sorted(unknown)[:5]}")
    m = g.unstack("cid").reindex(index=products, columns=design["cid"]).fillna(0.0)
    return m.to_numpy(dtype=float)


def _add_groups(sub: pd.DataFrame, groups: Iterable[CodeGroup]) -> pd.DataFrame:
    extra = [sub[sub["product"].isin(g.codes)].assign(product=g.id) for g in groups]
    return pd.concat([sub] + extra, ignore_index=True) if extra else sub


# --- national totals ----------------------------------------------------------------------
def period_totals(data: dict, year: int, months: Optional[Sequence[int]] = None,
                  measure: str = "ed_visits", products: Optional[Sequence[str]] = None,
                  groups: Iterable[CodeGroup] = ()) -> pd.DataFrame:
    """National estimate, SE, CV, records and CPSC 'unstable' flag for every product in one period.

    Same numbers as :func:`neissai.total` on the full NEISS file for that year.
    """
    ncol, wcol = MEASURES[measure]
    sub = _add_groups(_select(data["clusters"], year, months), groups)
    design = _design(data["psu"], [year], "stratum_psu")
    prods = pd.Index(sorted(sub["product"].unique()) if products is None else list(products), name="product")
    W = _matrix(sub, design, prods, wcol, "stratum_psu")
    n = sub.groupby("product")[ncol].sum().reindex(prods).fillna(0).astype(int).to_numpy()
    est = W.sum(axis=1)
    se = np.sqrt(_strat_var(W, design["stratum"].to_numpy()))
    with np.errstate(divide="ignore", invalid="ignore"):
        cv = np.where(est > 0, se / est, np.nan)
    unstable = [_unstable(int(a), float(b), float(c)) for a, b, c in zip(n, est, cv)]
    return pd.DataFrame({"product": prods, "records": n, "estimate": est, "se": se, "cv": cv,
                         "unstable": unstable})


# --- code changes -------------------------------------------------------------------------
def groups_for(data: dict, year: int, base_year: int, months: Optional[Sequence[int]] = None,
               groups: Sequence[CodeGroup] = CODE_GROUPS) -> list:
    """Code groups to use for this comparison: only those whose codes change between the periods."""
    c = data["clusters"]
    nA = _select(c, base_year, months).groupby("product")["n"].sum()
    nB = _select(c, year, months).groupby("product")["n"].sum()
    used = []
    for g in groups:
        a = {k: nA.get(k, 0) > 0 for k in g.codes}
        b = {k: nB.get(k, 0) > 0 for k in g.codes}
        if a != b and (any(a.values()) or any(b.values())):
            used.append(g)
    return used


def code_timeline(data: dict, min_records: int = 20) -> pd.DataFrame:
    """Records per year for every product code, and codes that start or stop inside the data.

    A code **starts** in year Y when it has no records in any earlier year and at least
    ``min_records`` records in Y (Y after the first data year); it **ends** after year Y when it
    has no records in any later year and at least ``min_records`` in Y. A code that appears
    from nothing with that many records, or vanishes, is almost always a CPSC coding change,
    not a hazard. Rare codes that come and go with a handful of records are not listed.
    """
    c = data["clusters"]
    c = c[c["product"] != ALL_PRODUCTS]
    per = c.pivot_table(index="product", columns="year", values="n", aggfunc="sum").fillna(0).astype(int)
    years = list(per.columns)
    rows = []
    for k, r in per.iterrows():
        active = [y for y in years if r[y] > 0]
        first, last = active[0], active[-1]
        starts = first > years[0] and r[first] >= min_records
        ends = last < years[-1] and r[last] >= min_records
        rows.append({"product": k, "first_year": first, "last_year": last, "records": int(r.sum()),
                     "starts": bool(starts), "ends": bool(ends)})
    t = pd.DataFrame(rows)
    t["possible_code_change"] = t["starts"] | t["ends"]
    known = {k: g.id for g in CODE_GROUPS for k in g.codes}
    t["known_group"] = t["product"].map(known).fillna("")
    t["product_name"] = t["product"].map(PRODUCT_NAMES).fillna("")
    return t.sort_values(["possible_code_change", "records"], ascending=[False, False]).reset_index(drop=True)


def suggest_code_groups(data: dict, min_records: int = 20) -> pd.DataFrame:
    """For each year, codes that ended the year before and codes that started that year.

    Codes that end and start at the same boundary are candidates for a new CPSC code group;
    ``covered_by_known_group`` says whether :data:`CODE_GROUPS` already handles them.
    """
    t = code_timeline(data, min_records)
    t = t[t["possible_code_change"]]
    rows = []
    for y in sorted(set(t.loc[t["starts"], "first_year"]) | set(t.loc[t["ends"], "last_year"] + 1)):
        new = t[t["starts"] & (t["first_year"] == y)]["product"].tolist()
        old = t[t["ends"] & (t["last_year"] == y - 1)]["product"].tolist()
        rows.append({"year": int(y), "codes_ended": " ".join(sorted(old)), "codes_started": " ".join(sorted(new)),
                     "covered_by_known_group": all(any(k in g.codes for g in CODE_GROUPS) for k in new + old)})
    return pd.DataFrame(rows)


# --- the scan -----------------------------------------------------------------------------
def bh_qvalues(p: Sequence[float]) -> np.ndarray:
    """Benjamini-Hochberg adjusted p-values (q-values); NaN stays NaN and is not counted."""
    p = np.asarray(p, dtype=float)
    q = np.full(p.shape, np.nan)
    ok = ~np.isnan(p)
    m = int(ok.sum())
    if m == 0:
        return q
    order = np.argsort(p[ok])
    ranked = p[ok][order] * m / np.arange(1, m + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.minimum(ranked, 1.0)
    q[ok] = out
    return q


def compare(data: dict, year: int, base_year: Optional[int] = None, months: Optional[Sequence[int]] = None,
            measures: Sequence[str] = ("ed_visits", "admissions"), alpha: float = 0.05, power: float = 0.80,
            fdr: float = 0.05, cluster: str = "hospital", groups: Sequence[CodeGroup] = CODE_GROUPS,
            reference: str = "same") -> pd.DataFrame:
    """Compare every product in ``year`` (optionally only ``months``) with the same months of ``base_year``.

    Returns one row per product and measure. A product is **flagged** when all of these hold:
    the excess change is positive; its BH q-value is below ``fdr``; the excess is at least the
    minimum detectable change (one-sided ``alpha``, ``power``); the current estimate is stable by
    CPSC's rule; and the comparison is not broken by a product-code change.

    ``reference="same"`` (default) measures admissions against all-NEISS admissions and ED visits
    against all-NEISS ED visits; ``reference="ed_visits"`` uses all-NEISS ED visits for both.
    """
    base_year = year - 1 if base_year is None else base_year
    c = data["clusters"]
    missing = {base_year, year} - set(c["year"].unique())
    if missing:
        raise ValueError(f"no data for {sorted(missing)}")
    used = groups_for(data, year, base_year, months, groups)
    subA = _add_groups(_select(c, base_year, months), used)
    subB = _add_groups(_select(c, year, months), used)
    design = _design(data["psu"], [base_year, year], cluster)
    strata = design["stratum"].to_numpy()
    prods = pd.Index(sorted(set(subA["product"]) | set(subB["product"])), name="product")
    in_group = {k: g.id for g in used for k in g.codes}
    z_a, z_p = _ND.inv_cdf(1 - alpha), _ND.inv_cdf(power)
    period = "full year" if months is None else "months " + ",".join(str(m) for m in months)

    frames = []
    for measure in measures:
        ncol, wcol = MEASURES[measure]
        A = _matrix(subA, design, prods, wcol, cluster)
        B = _matrix(subB, design, prods, wcol, cluster)
        allpos = prods.get_loc(ALL_PRODUCTS)
        if reference == "same":
            tA, tB = A[allpos], B[allpos]
        else:
            rcol = MEASURES[reference][1]
            tA = _matrix(subA, design, prods[[allpos]], rcol, cluster)[0]
            tB = _matrix(subB, design, prods[[allpos]], rcol, cluster)[0]
        TA, TB = tA.sum(), tB.sum()
        r = TB / TA
        YA, YB = A.sum(axis=1), B.sum(axis=1)
        nA = subA.groupby("product")[ncol].sum().reindex(prods).fillna(0).astype(int).to_numpy()
        nB = subB.groupby("product")[ncol].sum().reindex(prods).fillna(0).astype(int).to_numpy()
        totA = period_totals(data, base_year, months, measure, prods, used).set_index("product")
        totB = period_totals(data, year, months, measure, prods, used).set_index("product")

        expected = r * YA
        excess = YB - expected
        Zx = B - r * A - (YA / TA)[:, None] * (tB - r * tA)[None, :]
        se_x = np.sqrt(_strat_var(Zx, strata))
        se_d = np.sqrt(_strat_var(B - A, strata))
        with np.errstate(divide="ignore", invalid="ignore"):
            z = np.where(se_x > 0, excess / se_x, np.nan)
            top_share = np.where(excess > 0, Zx.max(axis=1) / excess, np.nan)
            pct = np.where(YA > 0, YB / YA - 1, np.nan)
            excess_pct = np.where(expected > 0, excess / expected, np.nan)
        p = np.array([0.5 * math.erfc(v / math.sqrt(2)) if not np.isnan(v) else np.nan for v in z])
        mdc = (z_a + z_p) * se_x

        status = []
        for k, a, b in zip(prods, nA, nB):
            if k == ALL_PRODUCTS:
                status.append("all NEISS (reference)")
            elif k in in_group:
                status.append(f"in code group {in_group[k]}")
            elif any(k == g.id for g in used):
                status.append("code group (codes change between periods)")
            elif a == 0 and b > 0:
                status.append("new code or no prior records: not compared")
            elif b == 0 and a > 0:
                status.append("code ended or no current records: not compared")
            else:
                status.append("compared")
        status = np.array(status)
        testable = np.isin(status, ["compared", "code group (codes change between periods)"]) & ~np.isnan(p)
        q = bh_qvalues(np.where(testable, p, np.nan))
        stableB = ~totB["unstable"].reindex(prods).to_numpy(dtype=bool)
        flag = testable & (excess > 0) & (q < fdr) & (excess >= mdc) & stableB

        notes = []
        for k, ts, f, na_, nb_ in zip(prods, top_share, flag, nA, nB):
            nn = []
            if year in PANDEMIC_YEARS:
                nn.append(PANDEMIC_NOTE)
            elif base_year in PANDEMIC_YEARS:
                nn.append(PANDEMIC_BASE_NOTE)
            if year == 2024 and base_year == 2023:
                nn.append(WEIGHTS_2024_NOTE)
            if (k, year) in PENDING_CHECKS:
                nn.append(PENDING_CHECKS[(k, year)])
            if k != ALL_PRODUCTS and 0 < na_ < 10 and nb_ >= 20 and nb_ >= 10 * na_:
                nn.append("few prior records: check whether the code is new or newly used")
            if f and not np.isnan(ts) and ts > 0.5:
                nn.append(f"one hospital gives {ts:.0%} of the excess; check coding at that hospital")
            notes.append("; ".join(nn))

        frames.append(pd.DataFrame({
            "year": year, "base_year": base_year, "period": period, "measure": measure, "product": prods,
            "product_name": [PRODUCT_NAMES.get(k, "") for k in prods], "status": status,
            "records_base": nA, "records": nB,
            "estimate_base": YA, "se_base": totA["se"].reindex(prods).to_numpy(),
            "estimate": YB, "se": totB["se"].reindex(prods).to_numpy(), "cv": totB["cv"].reindex(prods).to_numpy(),
            "unstable_base": totA["unstable"].reindex(prods).to_numpy(dtype=bool), "unstable": ~stableB,
            "change": YB - YA, "se_change": se_d, "pct_change": pct,
            "all_neiss_ratio": r, "expected": expected, "excess": excess, "se_excess": se_x,
            "excess_pct": excess_pct, "z": z, "p": p, "q": q, "mdc80": mdc,
            "mdc80_pct": np.where(expected > 0, mdc / np.where(expected > 0, expected, 1), np.nan),
            "top_hospital_share": top_share, "flag": flag, "note": notes,
        }))
    return pd.concat(frames, ignore_index=True)


def scan(data: dict, years: Sequence[int], months: Optional[Sequence[int]] = None, **kwargs) -> pd.DataFrame:
    """:func:`compare` for each year against the year before."""
    return pd.concat([compare(data, y, months=months, **kwargs) for y in years], ignore_index=True)


def flagged(results: pd.DataFrame) -> pd.DataFrame:
    """Only the flagged rows, by year and measure, largest excess first."""
    f = results[results["flag"]].copy()
    return f.sort_values(["year", "measure", "excess"], ascending=[True, True, False]).reset_index(drop=True)


def watch(data: dict, products: Sequence[str], years: Sequence[int], alpha: float = 0.05,
          **kwargs) -> pd.DataFrame:
    """Pre-specified watch list (for example a retrospective check of one code).

    For products chosen in advance there is no all-product multiple-testing correction: each
    product-year is a one-sided test at ``alpha``, on the plain change (``p_change``) and on
    the excess over all-NEISS volume (``p``). CPSC's unstable rule is reported, not applied.
    Use this to ask "would a watch on this code have signalled?", not as a scan of all products.
    """
    rows = []
    for y in years:
        r = compare(data, y, **kwargs)
        r = r[r["product"].isin(products)].copy()
        zc = np.where(r["se_change"] > 0, r["change"] / r["se_change"].where(r["se_change"] > 0, 1), np.nan)
        r["z_change"] = zc
        r["p_change"] = [0.5 * math.erfc(v / math.sqrt(2)) if not np.isnan(v) else np.nan for v in zc]
        r["signal_change"] = r["p_change"] < alpha
        r["signal_excess"] = r["p"] < alpha
        rows.append(r)
    keep = ["year", "base_year", "measure", "product", "product_name", "records_base", "records",
            "estimate_base", "estimate", "cv", "unstable", "change", "se_change", "z_change", "p_change",
            "signal_change", "excess", "se_excess", "z", "p", "signal_excess", "q", "flag", "note"]
    return pd.concat(rows, ignore_index=True)[keep]


def mdc_summary(data: dict, year: int, products: Sequence[str], measure: str = "ed_visits", **kwargs) -> pd.DataFrame:
    """Minimum detectable change (as % of expected) for a full year vs single months, for chosen products.

    Answers "can we scan monthly?": a monthly scan is only useful where the monthly MDC is
    small enough to catch rises that matter.
    """
    rows = []
    for label, months in [("full year", None)] + [(f"month {m}", [m]) for m in range(1, 13)]:
        r = compare(data, year, months=months, measures=[measure], **kwargs)
        r = r[r["product"].isin(products)]
        for _, x in r.iterrows():
            rows.append({"product": x["product"], "period": label, "expected": x["expected"],
                         "mdc80": x["mdc80"], "mdc80_pct": x["mdc80_pct"], "unstable": x["unstable"]})
    return pd.DataFrame(rows)


# --- emerging terms -----------------------------------------------------------------------
def term_category(term: str) -> str:
    """'writing style' if any word is a charting habit, abbreviation or number; 'clinical or context
    wording' if every word is a clinical, body, fall, place or person word; otherwise 'candidate'."""
    words = str(term).upper().split()
    if not words:
        return "writing style"
    for w in words:
        if w in STYLE_WORDS or any(p.search(w) for p in _STYLE_PATTERNS):
            return "writing style"
    if all(w in CLINICAL_WORDS or w in CONTEXT_WORDS for w in words):
        return "clinical or context wording"
    return "candidate"


_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _edits1(word: str) -> set:
    splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]
    deletes = [a + b[1:] for a, b in splits if b]
    swaps = [a + b[1] + b[0] + b[2:] for a, b in splits if len(b) > 1]
    replaces = [a + c + b[1:] for a, b in splits if b for c in _LETTERS]
    inserts = [a + c + b for a, b in splits for c in _LETTERS]
    return set(deletes + swaps + replaces + inserts) - {word}


def likely_misspelling(word: str, vocab: dict, factor: int = 20) -> Optional[str]:
    """The common word that ``word`` is one typo away from (at least ``factor`` times as frequent), if any.

    A sudden rise in a misspelled word usually means one new coder, not a new hazard.
    """
    if len(word) < 6:
        return None
    own = vocab.get(word, 0)
    # word endings (plurals, -ED/-ES) are grammar, and a dropped first letter (EBIKE -> BIKE)
    # is usually a prefix, not a typo
    cands = [e for e in _edits1(word)
             if len(os.path.commonprefix([e, word])) < len(word) - 2 and e != word[1:]]
    best = max(((vocab.get(e, 0), e) for e in cands), default=(0, None))
    return best[1] if best[0] >= factor * max(own, 1) else None


def records_by_year(data: dict) -> pd.Series:
    """Number of NEISS records per year (the all-records row of the export)."""
    c = data["clusters"]
    return c[c["product"] == ALL_PRODUCTS].groupby("year")["n"].sum()


def emerging_terms(terms: pd.DataFrame, year: int, records: pd.Series, base_year: Optional[int] = None,
                   min_count: int = 20, min_ratio: float = 1.5, fdr: float = 0.05, export_floor: int = 10,
                   filter_style: bool = True, tau_min_count: int = 300) -> pd.DataFrame:
    """Words and word pairs whose story count rose faster than the number of NEISS records.

    Two tests, both one-sided with Benjamini-Hochberg across all terms of the year:

    * ``z`` (Poisson): with ``k = records_now / records_before``,
      ``z = (n_now - k n_before) / sqrt(k (n_now + n_before))``. This treats every story as
      independent, so for common words it is far too sure of itself.
    * ``z_robust``: the log ratio ``log(n_now / (k n_before))`` divided by
      ``sqrt(1/n_now + 1/n_before + tau^2)``, where ``tau`` is the typical year-to-year drift of
      common words that year (robust SD of their log ratios, minus the Poisson part). A word must
      rise by more than words usually drift when coders and hospitals change.

    The export lists only counts of at least ``export_floor``; a term missing in the prior year
    gets ``export_floor - 1`` (the most it could have been), which keeps its test conservative.
    A term is **flagged** when both q-values are below ``fdr``, the ratio is at least
    ``min_ratio``, ``n_now >= min_count`` and (if ``filter_style``) its category is 'candidate'.
    This is a screening list for a person to read, not a design-based test.
    """
    base_year = year - 1 if base_year is None else base_year
    t = terms[terms["year"].isin([base_year, year])]
    wide_n = t.pivot_table(index="term", columns="year", values="n", aggfunc="sum")
    wide_w = t.pivot_table(index="term", columns="year", values="w", aggfunc="sum")
    empty = pd.Series(np.nan, index=wide_n.index)
    nB = wide_n.get(year, empty).fillna(0)
    nA_obs = wide_n.get(base_year, empty)
    keep = nB > 0
    nB, nA_obs = nB[keep], nA_obs[keep]
    nA = nA_obs.fillna(export_floor - 1)
    k = float(records[year]) / float(records[base_year])
    z = (nB - k * nA) / np.sqrt(k * (nA + nB))
    lr = np.log(nB / (k * nA))
    big = (nA_obs >= tau_min_count) & (nB >= tau_min_count)
    if big.sum() >= 20:
        mad = 1.4826 * float(np.median(np.abs(lr[big] - np.median(lr[big]))))
        tau2 = max(mad ** 2 - float(np.median(1 / nA[big] + 1 / nB[big])), 0.0)
    else:
        tau2 = 0.0
    zr = lr / np.sqrt(1 / nA + 1 / nB + tau2)
    upper = lambda v: np.array([0.5 * math.erfc(x / math.sqrt(2)) for x in v])  # noqa: E731
    out = pd.DataFrame({"year": year, "base_year": base_year, "term": nB.index,
                        "n_base": nA_obs.values, "n": nB.values,
                        "weighted_base": wide_w.get(base_year, empty).reindex(nB.index).values,
                        "weighted": wide_w.get(year, empty).reindex(nB.index).values,
                        "ratio_vs_records": (nB / (k * nA)).values,
                        "z": z.values, "p": upper(z.values), "z_robust": zr.values, "p_robust": upper(zr.values),
                        "tau": math.sqrt(tau2)})
    out["q"] = bh_qvalues(out["p"])
    out["q_robust"] = bh_qvalues(out["p_robust"])
    out["category"] = out["term"].map(term_category)
    out["new_term"] = out["n_base"].isna()
    ok = ((out["q"] < fdr) & (out["q_robust"] < fdr) & (out["ratio_vs_records"] >= min_ratio)
          & (out["n"] >= min_count))
    # misspellings of common words are a writing-style signal (checked only where needed)
    uni = terms[~terms["term"].str.contains(" ", regex=False)]
    vocab = uni.groupby("term")["n"].sum().to_dict()
    for i in out.index[ok & (out["category"] == "candidate")]:
        for word in out.at[i, "term"].split():
            fix = likely_misspelling(word, vocab)
            if fix:
                out.at[i, "category"] = f"writing style (misspelling of {fix})"
                break
    out["flag"] = ok & ((out["category"] == "candidate") if filter_style else True)
    out["note"] = PANDEMIC_NOTE if year in PANDEMIC_YEARS else ""
    return out.sort_values("z_robust", ascending=False).reset_index(drop=True)


# --- short list of product and hazard words ---------------------------------------------
#: Words in CPSC product names that say nothing about the product by themselves.
_NAME_STOP = frozenset("""
OTHER NOT SPECIFIED SPECIFIC ELSEWHERE CLASSIFIED EXCLUDING INCLUDING EXCL INCL ACTIVITY APPAREL
EQUIPMENT EQUIP ACCESSORIES ACCESSORY PRODUCTS PRODUCT DEVICES DEVICE MATERIALS MATERIAL PARTS
TYPE TYPES USED PERSONAL USE HOUSEHOLD GENERAL PURPOSE PUBLIC HOME POWERED POWER MANUAL ELECTRIC
FOR AND WITH WITHOUT FROM THAN CODE OLD UNTIL ALSO MADE SETS SYSTEMS SYSTEM UNITS UNIT ITEMS ITEM
PLAY SMALL LARGE PORTABLE FIXED NONE AREA AREAS SURFACES SURFACE STRUCTURES STRUCTURE
RIDING RIDE RIDES MEDICAL HEALTH CARE GAME GAMES ROOM ROOMS FALLS HIGH SOFT MOTOR CONTACT RANGE
LANDING FLUIDS FLUID METAL KIDNEY SOUNDS SOUND ALCOHOLIC REPAIR DEPLOYED ORTHOPEDIC UNPOWERED
VEHICLE VEHICLES TERRAIN WATER SUBSTANCE SUBSTANCES MOUNTAIN TRACK SCHOOL AID AIDS SNOW LOSS
SUPPLIES SUPPLY CHECK HOLDERS HOLDER COVERS COVER SUPPORTS SUPPORT TOOLS TOOL CONTAINERS CONTAINER
COMPLETED COMPLETE COMP STAND STANDS SHOOTING DRIVER DRIVERS BOARD BOARDS FIELD FIELDS MOTORS
""".split())
#: Device and hazard words added by hand (newer products, slang and spellings in injury stories).
EXTRA_PRODUCT_WORDS = frozenset("""
E-BIKE E-BIKES EBIKE EBIKES E-SCOOTER E-SCOOTERS ESCOOTER SCOOTER SCOOTERS HOVERBOARD HOVERBOARDS
MOPED MOPEDS E-MOTO DIRTBIKE ONEWHEEL UNICYCLE VAPE VAPES VAPING E-CIGARETTE MAGNET MAGNETS BEADS
BATTERY BATTERIES BUTTON GUMMY GUMMIES EDIBLE EDIBLES CANNABIS PICKLEBALL PADEL TRAMPOLINE
FIREWORK FIREWORKS GRINDER GRINDERS AIRFRYER FRYER PRESSURE COOKER CHARGER CHARGING LITHIUM
""".split())


def _product_vocab() -> frozenset:
    words = set(EXTRA_PRODUCT_WORDS)
    for name in PRODUCT_NAMES.values():
        for w in re.findall(r"[A-Za-z][A-Za-z-]+", str(name).upper()):
            if len(w) >= 4 and w not in _NAME_STOP:
                words.add(w)
                if w.endswith("S") and len(w) > 4:
                    words.add(w[:-1])
                else:
                    words.add(w + "S")
    return frozenset(words - _NAME_STOP - STYLE_WORDS - CLINICAL_WORDS - CONTEXT_WORDS)


PRODUCT_WORDS = _product_vocab()


#: Spellings that mean the same device, merged so a device is listed once.
_SYNONYMS = (
    (re.compile(r"\b(E-?BIKES?|ELECTRIC (BIKES?|BICYCLES?)|PEDAL[- ]ASSIST)\b"), "E-BIKE"),
    (re.compile(r"\b(E-?SCOOTERS?|ELECTRIC SCOOTERS?)\b"), "E-SCOOTER"),
    (re.compile(r"\bHOVERBOARDS?\b"), "HOVERBOARD"),
    (re.compile(r"\bMOPEDS?\b"), "MOPED"),
    (re.compile(r"\bWATER BEADS?\b"), "WATER BEADS"),
    (re.compile(r"\bFIREWORKS?\b"), "FIREWORKS"),
)


def product_word(term: str) -> str:
    """The device or product a term names: a known device phrase (e.g. 'ELECTRIC BICYCLE' ->
    'E-BIKE'), else a hand-listed device word, else a word from the CPSC product names; '' if none."""
    t = str(term).upper()
    for pat, name in _SYNONYMS:
        if pat.search(t):
            return name
    words = t.split()
    for w in words:
        if w in EXTRA_PRODUCT_WORDS:
            return w
    for w in words:
        if w in PRODUCT_WORDS:
            return w
    return ""


def hazard_words(emerging: pd.DataFrame, top: int = 15) -> pd.DataFrame:
    """Short reading list from :func:`emerging_terms`: flagged terms that name a product or device,
    one row per product word (the strongest term), with how many other flagged terms share it."""
    f = emerging[emerging["flag"]].copy()
    f["product_word"] = f["term"].map(product_word)
    f = f[f["product_word"] != ""].sort_values("z_robust", ascending=False)
    if f.empty:
        return f.assign(related_terms=pd.Series(dtype=int))
    f["related_terms"] = f.groupby("product_word")["term"].transform("size") - 1
    f = f.drop_duplicates("product_word")
    return f.head(top).reset_index(drop=True)


# --- website summary -----------------------------------------------------------------------
def signal_status(row) -> str:
    """'Coding' when a coding-practice note is attached, 'Check' when the earlier year was
    unstable or the newer year rests on fewer than 50 sampled cases, otherwise 'Signal'."""
    note = str(row.get("note", "") or "").lower()
    if "coding" in note:
        return "Coding"
    if bool(row.get("unstable_base", False)) or int(row.get("records", 0)) < 50:
        return "Check"
    return "Signal"


def site_summary(results: pd.DataFrame, words: Optional[pd.DataFrame] = None,
                 year: Optional[int] = None) -> dict:
    """Small JSON-ready summary of one year for the website's Hazard Watch tab: flagged
    ED-visit products (largest excess rise first) and the top product words."""
    year = int(results["year"].max()) if year is None else int(year)
    f = results[(results["year"] == year) & (results["measure"] == "ed_visits") & results["flag"]]
    f = f.sort_values("excess_pct", ascending=False)
    sig = [{"product": str(r["product"]), "name": str(r["product_name"] or r["product"]),
            "before": float(r["estimate_base"]), "after": float(r["estimate"]),
            "pct": float(r["pct_change"]), "records": int(r["records"]),
            "status": signal_status(r), "note": str(r.get("note", "") or "")} for _, r in f.iterrows()]
    out = {"year": year, "base_year": int(f["base_year"].iloc[0]) if len(f) else year - 1, "signals": sig}
    if words is not None and len(words):
        out["words"] = [{"term": str(r["term"]), "device": str(r["product_word"]),
                         "before": None if pd.isna(r["n_base"]) else int(r["n_base"]), "after": int(r["n"])}
                        for _, r in words.head(10).iterrows()]
    return out


def update_site_hazards(df: pd.DataFrame, out_dir: PathLike, work_dir: Optional[PathLike] = None) -> dict:
    """Rebuild the website's Hazard Watch files from NEISS records: the scan tables for every
    year after the first and ``summary.json`` for the latest year. Used by the monthly refresh."""
    import json
    import tempfile
    out = Path(out_dir)
    work = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="neissai_hazards_"))
    data = read_hazard_export(build_hazard_export(df, work))
    years = sorted(int(y) for y in data["psu"]["year"].unique())[1:]
    write_scan_outputs(data, out, years)
    full = pd.read_csv(out / f"hazard_scan_{years[-1]}.csv", dtype={"product": str})
    wpath = out / f"hazard_words_{years[-1]}.csv"
    words = pd.read_csv(wpath) if wpath.exists() else None
    summary = site_summary(full, words, years[-1])
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    return summary


# --- outputs ------------------------------------------------------------------------------
def names_todo(results: pd.DataFrame) -> list:
    """Flagged product codes that still have no name (CPSC's code list was not available offline)."""
    f = results[results["flag"] & (results["product_name"] == "")]
    return sorted(set(f["product"]), key=lambda k: (len(k), k))


#: Products followed on the watch list by default (micromobility codes and groups).
WATCH_PRODUCTS = ("3215", "5045", "5046", "5022", "5040", "3215+5045+5046")


def write_scan_outputs(data: dict, out_dir: PathLike, years: Sequence[int], **kwargs) -> dict:
    """Write the scan results to ``out_dir``. Returns flag counts by year and measure.

    Files: ``hazard_scan_<year>.csv`` (every product, both measures), ``hazard_flags.csv``,
    ``emerging_terms_<year>.csv`` (terms that passed the screen, with their category),
    ``hazard_words_<year>.csv`` (short reading list of product and device words), ``watch_list.csv``, ``code_changes.csv``,
    ``code_group_suggestions.csv`` and ``product_names_todo.txt``.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    allres = []
    for y in years:
        r = compare(data, y, **kwargs)
        r.to_csv(out / f"hazard_scan_{y}.csv", index=False)
        allres.append(r)
        if "terms" in data:
            et = emerging_terms(data["terms"], y, records_by_year(data))
            # keep the terms that passed the screen (flagged or removed by the style filter), for review
            et = et[(et["q"] < 0.05) & (et["q_robust"] < 0.05) & (et["ratio_vs_records"] >= 1.5) & (et["n"] >= 20)]
            et.to_csv(out / f"emerging_terms_{y}.csv", index=False)
            hazard_words(et).to_csv(out / f"hazard_words_{y}.csv", index=False)
    res = pd.concat(allres, ignore_index=True)
    flagged(res).to_csv(out / "hazard_flags.csv", index=False)
    watch(data, WATCH_PRODUCTS, years, **kwargs).to_csv(out / "watch_list.csv", index=False)
    code_timeline(data).query("possible_code_change").to_csv(out / "code_changes.csv", index=False)
    suggest_code_groups(data).to_csv(out / "code_group_suggestions.csv", index=False)
    todo = names_todo(res)
    if todo:
        (out / "product_names_todo.txt").write_text(
            "Flagged codes without a name in model/product_codes.csv:\n" + "\n".join(todo) + "\n")
    counts = res.groupby(["year", "measure"])["flag"].sum().unstack().fillna(0).astype(int)
    return counts.to_dict(orient="index")
