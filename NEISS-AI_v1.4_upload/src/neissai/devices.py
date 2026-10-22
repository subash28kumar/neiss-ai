"""Label each injury by micromobility device, using product codes AND the injury narrative.

Why narratives matter: CPSC changed its product codes in this period.
  * 2019: powered scooters and hoverboards shared older codes (5042, 1329).
  * Until 2023: e-bikes were mixed with mopeds under code 3215 ("mopeds or power-assisted cycles").
  * From 2024: e-bikes have their own code (5045); other power-assisted cycles use 5046.
Codes alone cannot give a consistent e-bike trend; the narratives can.

Step A: rules (codes + whole-word keywords) give a device label.
Step B: for code-3215 records the rules cannot decide, a text classifier trained on 2024+
        records (codes 5045 vs 5046) decides between "E-bike" and "Moped / minibike".
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import circumstances as _circ

from .classifier import EbikeMopedClassifier

DEVICES = ["E-bike", "E-scooter", "Bicycle", "Kick scooter", "Hoverboard", "Skateboard", "Moped / minibike"]

E_WORDS = (r"\bE-?BIKES?\b|\bE BIKES?\b|\bE-?BICYCLES?\b|ELECTRI(C|CAL) (BI(KE|CYCLE)|PEDAL|ASSIST)|"
           r"PEDAL[- ]ASSIST|POWER[- ]ASSIST(ED)? (BI(KE|CYCLE))|BATTERY[- ]POWERED (BI(KE|CYCLE))")
ESC_WORDS = (r"\bE-?SCOOTERS?\b|\bE SCOOTERS?\b|ELEC(TRIC|TRONIC)? SCOOTER|MOTORI[ZS]ED SCOOTER|POWERED SCOOTER|"
             r"STAND[- ]?UP (ELECTRIC|MOTORIZED)|LIME SCOOTER|BIRD SCOOTER|RENTAL SCOOTER|BATTERY[- ]POWERED SCOOTER")
MOBILITY_WORDS = r"MOBILITY SCOOTER|INVALID|ASSIST(IVE|ED) MOBILITY|POWER CHAIR|WHEELCHAIR|HANDICAP"
MOPED_WORDS = r"MOPED|MINI ?BIKE|DIRT ?BIKE|MOTOR ?BIKE|MOTORCYCLE|GAS (POWERED|SCOOTER)|VESPA"
EXERCISE_WORDS = r"STATIONARY|EXERCISE BIKE|SPIN BIKE|PELOTON|WORKOUT BIKE"
HOVER_WORDS = r"HOVER ?BOARD"

BIKE_CODES = ("5040", "5033")
SCOOTER_CODES = ("5022", "5023", "5024", "1329", "5042")
RELEVANT_CODES = BIKE_CODES + SCOOTER_CODES + ("5025", "1333", "3215", "5045", "5046", "5035")
CANDIDATE_WORDS = r"BIKE|BICYCL|SCOOTER|HOVER ?BOARD|SKATE ?BOARD|MOPED"


def _noncapturing(pattern: str) -> str:
    return pattern.replace("(", "(?:").replace("(?:?:", "(?:")


def _kw(narr: pd.Series, pattern: str) -> pd.Series:
    return narr.str.contains(_noncapturing(pattern), regex=True)


def _has(codes: pd.DataFrame, *values: str) -> pd.Series:
    return codes.isin(list(values)).any(axis=1)


def label_devices(df: pd.DataFrame, classifier: EbikeMopedClassifier | None = None,
                  threshold: float = 0.5) -> pd.DataFrame:
    """Add ``device``, ``label_source`` and ``p_ebike`` columns.

    ``df`` must be a standardized NEISS table (see :func:`neissai.io.standardize`).
    Records that are not micromobility injuries get ``device = "Other"``.
    Exercise bikes and mobility scooters are labelled ``"Excluded"``.
    """
    out = df.copy()
    codes_all = out[["Product_1", "Product_2", "Product_3"]].astype("string").fillna("0")
    narr_all = out["Narrative"].astype("string").fillna("").str.upper()
    # Only records with a relevant code or word need the (slower) rules.
    cand = _has(codes_all, *RELEVANT_CODES) | narr_all.str.contains(CANDIDATE_WORDS, regex=True)
    out["device"] = "Other"
    out["label_source"] = ""
    out["p_ebike"] = np.nan
    if not cand.any():
        return out
    narr, codes = narr_all[cand], codes_all[cand]
    bike, scooter = _has(codes, *BIKE_CODES), _has(codes, *SCOOTER_CODES)
    e_words, moped_words = _kw(narr, E_WORDS), _kw(narr, MOPED_WORDS)

    label = pd.Series("Other", index=narr.index, dtype="object")
    # Order matters: later rules override earlier ones.
    label[bike] = "Bicycle"
    label[_has(codes, "5024", "5023", "1329")] = "Kick scooter"
    label[_has(codes, "5022") | (_has(codes, "5042") & _kw(narr, ESC_WORDS))] = "E-scooter"
    label[_has(codes, "5025") | (_has(codes, "5042") & _kw(narr, HOVER_WORDS))] = "Hoverboard"
    label[_has(codes, "1333")] = "Skateboard"
    label[_has(codes, "5046", "5035") | (_has(codes, "3215") & moped_words)] = "Moped / minibike"
    label[_has(codes, "5045")] = "E-bike"
    # Narrative overrides inside bicycle and scooter codes
    label[(bike | _has(codes, "3215")) & e_words] = "E-bike"
    label[scooter & _kw(narr, ESC_WORDS)] = "E-scooter"
    label[scooter & _kw(narr, MOBILITY_WORDS)] = "Excluded"
    label[_kw(narr, EXERCISE_WORDS) & label.isin(["Bicycle", "E-bike"])] = "Excluded"
    label[bike & ~_has(codes, "5045", "3215") & _kw(narr, r"NON-? ?ELECTRIC")] = "Bicycle"

    undecided = _has(codes, "3215") & ~e_words & ~moped_words
    source = pd.Series(np.where(label == "Other", "", "rules"), index=narr.index)
    source[undecided] = "classifier"
    if undecided.any():
        clf = classifier or EbikeMopedClassifier.load_default()
        p = clf.predict_proba(narr[undecided].tolist())
        out.loc[undecided[undecided].index, "p_ebike"] = p
        label[undecided] = np.where(p >= threshold, "E-bike", "Moped / minibike")
    out.loc[narr.index, "device"] = label
    out.loc[narr.index, "label_source"] = source
    return out


def add_outcomes(df: pd.DataFrame) -> pd.DataFrame:
    """Add simple outcome and circumstance flags (0/1) and an age group."""
    out = df.copy()
    out["hospitalized"] = out["Disposition"].isin(["2", "4", "5", "8"]).astype(int)  # transferred, admitted, held, died
    out["died"] = (out["Disposition"] == "8").astype(int)
    out["head_injury"] = out[["Body_Part", "Body_Part_2"]].isin(["75", "76", "77", "94"]).any(axis=1).astype(int)
    # Circumstances read from the narrative (InjuryCoder rules, validated in v1.4; see circumstances.py)
    raw = out["Narrative"].astype("string").fillna("")
    helmet = raw.map(_circ.helmet)
    out["helmet_status"] = helmet
    out["helmet_no"] = (helmet == "no").astype(int)
    out["helmet_yes"] = (helmet == "yes").astype(int)
    out["motor_vehicle"] = raw.map(_circ.motor_vehicle).astype(int)
    out["alcohol"] = (out["Alcohol"] == "1").astype(int)
    out["age_group"] = pd.cut(out["Age"], [-1, 17.99, 64.99, 200],
                              labels=["0-17", "18-64", "65+"]).astype("string")
    return out


def micromobility(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    """Label devices and outcomes, and keep only micromobility injuries."""
    out = add_outcomes(label_devices(df, **kwargs))
    return out[out["device"].isin(DEVICES)].reset_index(drop=True)
