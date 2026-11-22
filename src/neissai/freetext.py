"""Label ANY injury notes, not only NEISS: free text, with optional ICD-10-CM codes (added in v1.7).

NEISS-AI's main labeller (:func:`neissai.devices.label_devices`) reads the injury story together
with CPSC's NEISS product codes. Other data, such as a state's emergency department records or
another country's hospital notes, has no NEISS product codes. This module labels such records
from what is available:

* the note text alone (triage note, chief complaint, or a longer narrative), and
* optionally, US ICD-10-CM external-cause codes (V00-V29), if the data has them.

Everything runs on the user's own computer. No data is sent anywhere.

What it returns for each record (see :func:`label_note`):

* ``device``: "E-bike", "E-scooter", "Bicycle", "Kick scooter", "Hoverboard", "Skateboard",
  "Moped / minibike", "Scooter (type not stated)", "Other standing micromobility",
  "Excluded" (mobility scooter, exercise bike) or "Other" (no micromobility device found).
* ``device_how``: what decided it: "words", "code", "code+words" or "classifier".
* ``ebike_type`` (e-bikes only): "regular e-bike", "likely e-moto" or "unclear".
* ``helmet``: "yes", "no" or "not mentioned"; ``motor_vehicle``: True/False.
* ``rider_mph``: the highest speed the note gives for the rider (None if not stated).
* ``role``: "rider", or "struck by rider" when an ICD-10-CM code says the patient was on foot
  and hit by someone riding the device (None when there is no code to tell).

Honest limits (please read before use):

* Text-only labels depend on the words in the note. "Fell off scooter" does not say whether the
  scooter was electric, so it becomes "Scooter (type not stated)" unless a code settles it.
* Short triage notes say less than NEISS stories, so more records stay unclear.
* The rules were written for US English NEISS stories. Other places use other words (for
  example "push bike", "e-scooter hire"); check a sample by hand and adjust the word lists.
* The ICD-10-CM mapping follows the NEMSIS micromobility case definition (June 27, 2023):
  standing e-scooter codes exist from October 2020 and e-bike codes from October 2022. Before
  those dates e-scooters and e-bikes sit under broader codes, so the note text decides.
  ICD-10-AM (Australia) and other national versions differ: pass your own ``code_map``.
* Accuracy: see validation/freetext/RESULTS.md for how text-only labels compare with
  NEISS-AI's full labels (which also use the product codes).
"""
from __future__ import annotations

import re
from typing import Callable, Iterable, Optional, Sequence

import numpy as np
import pandas as pd

from . import circumstances as _circ
from .classifier import EbikeMopedClassifier
from .devices import ESC_NEG_WORDS, E_WORDS, ESC_WORDS, EXERCISE_WORDS, HOVER_WORDS, MOBILITY_WORDS, MOPED_WORDS
from .ebike_type import ebike_type as _ebike_type
from .ebike_type import rider_speeds as _rider_speeds

DEVICES_TEXT = ["E-bike", "E-scooter", "Bicycle", "Kick scooter", "Hoverboard", "Skateboard",
                "Moped / minibike", "Scooter (type not stated)", "Other standing micromobility",
                "Excluded", "Other"]


def _rx(p: str) -> re.Pattern:
    return re.compile(p.replace("(", "(?:").replace("(?:?:", "(?:"))


# Word patterns (upper-case text). Built on the NEISS-AI patterns in devices.py.
_E = _rx(E_WORDS)
_ESC = _rx(ESC_WORDS + r"|\bE-?SCOOT\w*")
_HOVER = _rx(HOVER_WORDS)
_EMOTO_WORDS = re.compile(r"SUR-?RON|TALARIA|\bE-?MOTO|ELEC\w* (?:MOTORCYCLE|DIRT ?BIKE|MOTOR ?BIKE)")
_SEGWAY = re.compile(r"SEGWAY|ONE ?WHEEL|ELECTRIC UNICYCLE|E-?UNICYCLE|E-?SKATE ?BOARD|ELECTRIC SKATE ?BOARD")
_MOPED = _rx(MOPED_WORDS)
_MOBILITY = _rx(MOBILITY_WORDS)
_EXERCISE = _rx(EXERCISE_WORDS)
_ESC_NEG = _rx(ESC_NEG_WORDS)
_KICK = re.compile(r"KICK ?SCOOTER|RAZOR SCOOTER|PUSH ?SCOOTER|(?:MANUAL|FOOT[- ]POWERED) SCOOTER|" + _ESC_NEG.pattern)
_SCOOTER = re.compile(r"SCOOTER")
_SKATE = re.compile(r"SKATE ?BOARD|LONG ?BOARD")
_BIKE = re.compile(r"\bBI(?:KE|CYCLE)S?\b|BICYCL\w*|\bCYCLIST|\bBIKING\b|\bCYCLING\b|PUSH ?BIKE|PEDAL ?BIKE|\bBMX\b|MOUNTAIN ?BIKE")
_MOTORIZED_BIKE = re.compile(r"MOTORI[ZS]ED (?:BI(?:KE|CYCLE)|CYCLE)|POWER(?:ED)?[- ]ASSIST\w* CYCLE|MOTOR ?BICYCLE")
_NON_ELECTRIC = re.compile(r"NON-? ?ELECTRIC (?:BI(?:KE|CYCLE))|REGULAR (?:BI(?:KE|CYCLE))|PEDAL (?:BI(?:KE|CYCLE)) \(NOT ELECTRIC\)")
_ONTO = re.compile(r"(?:RIDING|RODE|RIDE|RIDER OF|ON (?:A|AN|THE|HIS|HER|THEIR|MY)?|OFF (?:OF )?(?:A|AN|THE|HIS|HER|THEIR)?|FROM (?:A|AN|THE|HIS|HER|THEIR)?|OPERATING|DRIVING|USING)\s*(?:\w+\s+){0,2}$")
_DX = re.compile(r"\bDX[\s:;.,]|DIAGNOSIS")
_KMH = re.compile(r"(\d{1,3}) ?(?:KM/H|KMH|KPH|KM PER HOUR|KILOMETRES PER HOUR|KILOMETERS PER HOUR)")  # converted to mph

# ICD-10-CM external-cause codes (US), following the NEMSIS micromobility case definition
# (June 27, 2023) and the ICD-10-CM tabular list. Each rule: (regex on the code without dot,
# device, role). Checked in order; first match wins.
ICD10CM_RULES: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"^V0083"), "Excluded", "rider"),                       # motorized mobility scooter
    (re.compile(r"^V00031"), "E-scooter", "struck by rider"),           # on foot, hit by standing e-scooter rider
    (re.compile(r"^V00038"), "Other standing micromobility", "struck by rider"),
    (re.compile(r"^V0084[12]"), "E-scooter", "rider"),                  # fall from / collision on standing e-scooter
    (re.compile(r"^V00848"), "Other standing micromobility", "rider"),  # hoverboard, Segway
    (re.compile(r"^V0[1-6][019]31"), "E-scooter", "rider"),             # on standing e-scooter, hit by ...
    (re.compile(r"^V0[1-6][019]38"), "Other standing micromobility", "rider"),
    (re.compile(r"^V0002"), "Skateboard", "struck by rider"),           # on foot, hit by skateboarder
    (re.compile(r"^V0013"), "Skateboard", "rider"),
    (re.compile(r"^V0[1-6][019]2"), "Skateboard", "rider"),
    (re.compile(r"^V0014"), "Kick scooter", "rider"),                   # scooter (nonmotorized)
    (re.compile(r"^V2\d\d1"), "E-bike", "rider"),                       # electric (assisted) bicycle, from Oct 2022
    (re.compile(r"^V29\d\d1"), "E-bike", "rider"),
    (re.compile(r"^V2\d"), "Moped / minibike", "rider"),                # other motorcycle / moped / motor scooter
    (re.compile(r"^V1\d"), "Bicycle", "rider"),                         # pedal cycle rider
    (re.compile(r"^V01"), "Bicycle", "struck by rider"),                # pedestrian hit by pedal cycle
]


def _clean_text(text) -> str:
    if text is None or (isinstance(text, float) and np.isnan(text)):
        return ""
    return str(text).upper()


def _story(t: str) -> str:
    """Text before the diagnosis, as in NEISS-AI's e-moto rule; the whole text if no 'DX'."""
    return _DX.split(t, maxsplit=1)[0]


def _codes(value) -> list[str]:
    """Split a cell holding one or more ICD codes ('V28.01XA; S52.5') into dot-free upper codes."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return []
    if isinstance(value, (list, tuple)):
        parts = [str(v) for v in value]
    else:
        parts = re.split(r"[\s,;|]+", str(value))
    return [p.upper().replace(".", "").strip() for p in parts if p.strip()]


def device_from_codes(codes, code_map: Optional[Sequence[tuple]] = None):
    """(device, role) from ICD-10-CM codes, or (None, None) if no micromobility code is present.

    ``code_map`` replaces the built-in US ICD-10-CM rules: a list of (code start, device, role),
    for example ``[("V10", "Bicycle", "rider")]``; a compiled regex may be given instead of a code start.
    """
    rules = ICD10CM_RULES if code_map is None else [
        (p if isinstance(p, re.Pattern) else re.compile("^" + re.escape(str(p).upper().replace(".", ""))), dev, role)
        for p, dev, role in code_map]
    for code in _codes(codes):
        for rx, dev, role in rules:
            if rx.search(code):
                return dev, role
    return None, None


def _first_device(story: str) -> Optional[str]:
    """The device the patient was on, from the words. When several are named, prefer one that
    follows 'riding / on / fell off / from', then the first one named."""
    found = []  # (preferred?, position, device)

    def add(rx, dev, text=None):
        for m in rx.finditer(story if text is None else text):
            pref = bool(_ONTO.search(story[max(0, m.start() - 40):m.start()]))
            found.append((not pref, m.start(), dev))
            break

    add(_SEGWAY, "Other standing micromobility")
    add(_HOVER, "Hoverboard")
    add(_SKATE, "Skateboard")
    add(_ESC, "E-scooter", _ESC_NEG.sub(lambda m: " " * len(m.group()), story))   # "UNPOWERED SCOOTER" is not an e-scooter
    add(_KICK, "Kick scooter")
    if not any(d in ("E-scooter", "Kick scooter") for *_, d in found):
        add(_SCOOTER, "Scooter (type not stated)")
    add(_E, "E-bike")
    add(_EMOTO_WORDS, "E-bike")   # e-motos sit inside e-bike counts, flagged by ebike_type (as in NEISS-AI)
    add(_MOTORIZED_BIKE, "motorized bike")
    add(_MOPED, "Moped / minibike")
    if not any(d in ("E-bike",) for *_, d in found):
        add(_BIKE, "Bicycle")
    if not found:
        return None
    found.sort()
    best = found[0][2]
    # A plain bike mention next to e-bike words for the same vehicle is the e-bike.
    if best == "Bicycle" and (_E.search(story) or _EMOTO_WORDS.search(story)) and not _NON_ELECTRIC.search(story):
        return "E-bike"
    return best


def label_note(text, codes=None, classifier: Optional[EbikeMopedClassifier] = None,
               threshold: float = 0.5, code_map: Optional[Sequence[tuple]] = None) -> dict:
    """Label one injury note. ``codes``: optional ICD-10-CM code(s) for the same visit."""
    t = _clean_text(text)
    story = _story(t)
    p_ebike = None

    if _MOBILITY.search(story) and not _ESC.search(_ESC_NEG.sub(" ", story.replace("MOBILITY SCOOTER", ""))):
        words = "Excluded"
    elif _EXERCISE.search(story):
        words = "Excluded"
    else:
        words = _first_device(story)

    how = "words"
    if words == "motorized bike":
        # The same question NEISS-AI's classifier answers for CPSC code 3215: e-bike or moped?
        clf = classifier or EbikeMopedClassifier.load_default()
        p_ebike = float(clf.predict_proba([t])[0])
        words = "E-bike" if p_ebike >= threshold else "Moped / minibike"
        how = "classifier"

    code_dev, role = device_from_codes(codes, code_map) if codes is not None else (None, None)

    if code_dev is None:
        device = words or "Other"
        if words is None:
            how = ""
    elif words is None or words == code_dev:
        device, how = code_dev, ("code" if words is None else "code+words")
    else:
        # Codes and words disagree. Words that name the device more exactly win where NEISS-AI's
        # own rules let the story override the code (e-bike words on a bicycle or motorcycle code,
        # e-scooter words on a scooter code, a stated type for an unstated scooter); otherwise the code.
        if code_dev in ("Bicycle", "Moped / minibike") and words == "E-bike":
            device, how = "E-bike", "code+words"
        elif code_dev == "Other standing micromobility" and words == "Hoverboard":
            device, how = "Hoverboard", "code+words"
        elif code_dev == "Kick scooter" and words == "E-scooter":
            device, how = "E-scooter", "code+words"
        elif words == "Scooter (type not stated)" and code_dev in ("E-scooter", "Kick scooter"):
            device, how = code_dev, "code"
        elif words == "Excluded":
            device, how = "Excluded", "words"
        else:
            device, how = code_dev, "code"

    speeds = _rider_speeds(_KMH.sub(lambda m: f"{round(int(m.group(1)) * 0.621371)} MPH", story))
    return {
        "device": device,
        "device_how": how,
        "p_ebike": p_ebike,
        "ebike_type": _ebike_type(t) if device == "E-bike" else None,
        "helmet": _circ.helmet(t),
        "motor_vehicle": _circ.motor_vehicle(t),
        "rider_mph": max(s[1] for s in speeds) if speeds else None,
        "role": role,
    }


def label_notes(df: pd.DataFrame, text_col: str, code_cols: Optional[Iterable[str]] = None,
                threshold: float = 0.5, code_map: Optional[Sequence[tuple]] = None) -> pd.DataFrame:
    """Label every row of a table of injury notes; returns the table with new columns.

    ``text_col``: the column with the note text. ``code_cols``: optional column(s) with ICD-10-CM
    codes (one code or a list per cell). Rows keep their order and all original columns."""
    if text_col not in df.columns:
        raise KeyError(f"text column {text_col!r} not found; columns are: {list(df.columns)}")
    code_cols = [code_cols] if isinstance(code_cols, str) else list(code_cols or [])
    for c in code_cols:
        if c not in df.columns:
            raise KeyError(f"code column {c!r} not found; columns are: {list(df.columns)}")
    clf = EbikeMopedClassifier.load_default()
    rows = []
    for i in range(len(df)):
        codes = None
        if code_cols:
            codes = [x for c in code_cols for x in _codes(df[c].iloc[i])]
        rows.append(label_note(df[text_col].iloc[i], codes, classifier=clf, threshold=threshold, code_map=code_map))
    lab = pd.DataFrame(rows, index=df.index)
    return pd.concat([df, lab], axis=1)


def summary(labeled: pd.DataFrame) -> pd.DataFrame:
    """Counts of records by device (and e-bike type), for a quick look at the results."""
    out = labeled["device"].value_counts().rename_axis("device").reset_index(name="records")
    return out
