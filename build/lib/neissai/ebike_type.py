"""E-bike or e-moto? A rule that reads NEISS e-bike narratives (v2, November 2026).

Some vehicles counted as "e-bikes" are really electric motorcycles ("e-motos", such as
Sur-Ron or Talaria models) or e-bikes ridden far above legal e-bike speeds. NEISS has no code
for this, and the stated e-bike class (1, 2 or 3) almost never appears in the narrative, so the
rule uses only what the story says (definitions: validation/ebike_type_v2/DEFINITIONS.md):

* ``"likely e-moto"``  - e-moto wording (SUR-RON, TALARIA, E-MOTO, electric motorcycle or
  dirt bike, gas- or engine-powered, a clutch), or the rider's own speed above 28 mph (the top
  assisted speed of a legal Class 3 e-bike) on a vehicle called an e-bike, not going downhill
  and not someone else's guess.
* ``"unclear"``        - "motorized bike/bicycle" or "motor bike" wording at any speed, wording
  that could mean either ("dirt bike or e-bike", "bike vs e-bike", "motorcyclist", a dirt-bike
  helmet), a speed range that crosses 28 mph, a downhill or second-hand speed above 28 mph, or
  "fast"/"high speed" about the rider with no speed given.
* ``"regular e-bike"`` - everything else.

Only the story before the diagnosis ("DX") is read, because diagnosis coding phrases such as
"FALL FROM MOTORIZED BIKE" describe a coding category, not the vehicle. Speeds and "fast"
wording that belong to another vehicle or rider ("STRUCK BY A CAR GOING 30 MPH") are ignored.

Test (v2): rebuilt on 920 development stories, locked (code fingerprint recorded), then scored
once on 240 new stories (2019-2025) labelled blind: 98.9% in the right group across all e-bike
stories (95% CI 97.9-99.7%; raw 233/240); likely e-moto share 1.7% by the rule vs 1.6% by the
reviewers; single "likely e-moto" calls right about 19 times in 20 in that test. See
validation/ebike_type_v2/RESULTS.md. A narrative names an e-moto only when the writer says so,
so "likely e-moto" is a lower bound, not a full count.
"""
from __future__ import annotations

import re

import pandas as pd

LIMIT_MPH = 28
_EMOTO = re.compile(r"SUR-?RON|TALARIA|\bE-?MOTO|ELEC\w* (?:MOTORCYCLE|DIRT ?BIKE)|DIRT ?BIKE|GAS[- ]?(?:POWERED|MOTORIZED)"
                    r"|ENGINE[- ]?(?:POWERED|MOTORIZED|BIKE|BICYCLE)|(?:MOTORIZED|GAS)\W+(?:\w+\W+){0,2}ENGINE|\bCLUTCH")
_EITHER = re.compile(r"DIRT ?BIKE,? (?:OR|VS\.?|VERSUS)\b|\b(?:OR|VS\.?|VERSUS) (?:AN? )?DIRT ?BIKE|\b(?:BIKE|BICYCLE),? (?:OR|VS\.?|VERSUS) (?:AN? )?E-?BIKE|MOTORCYCLE,? OR (?:AN? )?E-?BIKE|E-?BIKE,? OR (?:AN? )?MOTORCYCLE")
_GEAR = re.compile(r"DIRT ?BIKE\W{0,2} ?HELMET")
_VEH = re.compile(r"(?<!PARKED )\b(?:CAR|VEHICLE|AUTO|TRUCK|SUV|VAN|BUS|DRIVER|MOTORIST|MOTORCYCLE|MOPED)\b"
                  r"|\b(?:ANOTHER|OTHER) (?:E-?BIKE|BIKE|BICYCLE|BICYCLIST|CYCLIST|RIDER|SCOOTER|E-?SCOOTER)")
_RIDER = re.compile(r"BIKE|BICYCLE|RIDING|RIDER|\bPT\b|PATIENT")
_SPEED = re.compile(r"(\d{1,3})(?: ?(?:-|TO|OR) ?(\d{1,3}))? ?(?:MPH|MILES PER HOUR|MILES AN HOUR)")
_UNCLEAR_EARLY = re.compile(r"MOTORCYCLIST|MOBILITY SCOOTER")
_UNCLEAR = re.compile(r"(?<!ANOTHER )(?<!OTHER )(?:MOTORI[ZS]ED +(?:(?!ELEC|E\b)[A-Z]+ +)?(?:BIK\w*|BIC\w*|BYC\w*|\*)|MOTOR ?BIKE|MOTOR BICYCLE)")
_SAME_AS_EBIKE = re.compile(r"MOTORI[ZS]ED +(?:BIKE|BICYCLE) ?(?:/|\(|,|OR|AKA) ?(?:AN? )?(?:E-?BIKE|ELECTRIC)"
                            r"|(?:E-?BIKE|ELECTRIC (?:BIKE|BICYCLE)) ?/ ?MOTOR ?BIKE")
_FAST = re.compile(r"\bFAST\b|HIGH SPEED|HIGH RATE OF SPEED|FULL SPEED|TOP SPEED|SPEEDING")
_GUESS = re.compile(r"BYSTANDERS?\W+(?:\w+\W+){0,3}(?:THOUGHT|SAID|STATED|ESTIMATED|REPORTED)|WITNESS\w*\W+(?:\w+\W+){0,3}(?:THOUGHT|ESTIMATED)"
                    r"|ESTIMATED BY|\bDISPUTED\b|NOT SURE HOW FAST|UNSURE HOW FAST")
_DOWNHILL = re.compile(r"DOWN ?HILL|DOWN (?:A |THE )?(?:STEEP |LARGE |BIG )?(?:HILL|INCLINE|SLOPE|GRADE)")
_DX = re.compile(r"DX[\s:;.,]|DIAGNOSIS")

LABELS = ("regular e-bike", "likely e-moto", "unclear")


def _story(text):
    """Upper-case text before the diagnosis. Diagnosis codes such as 'FALL FROM MOTORIZED BIKE'
    or 'DRIVER OF DIRT BIKE OR MOTOR/CROSS BIKE' are standard coding phrases, not the vehicle."""
    t = "" if text is None or (isinstance(text, float) and pd.isna(text)) else str(text).upper()
    return _DX.split(t, maxsplit=1)[0]


def rider_speeds(text):
    """Speeds (low, high) in mph that belong to the rider, not to another vehicle."""
    t = (text or "").upper()
    out = []
    for m in _SPEED.finditer(t):
        lo = int(m.group(1)); hi = int(m.group(2) or m.group(1))
        lo, hi = min(lo, hi), max(lo, hi)
        before = t[max(0, m.start() - 70):m.start()]
        last_vehicle = max((v.end() for v in _VEH.finditer(before)), default=-1)
        last_rider = max((b.end() for b in _RIDER.finditer(before)), default=-1)
        if last_vehicle < 0 or last_rider > last_vehicle:
            out.append((lo, hi))
    return out


def _rider_fast(t):
    """True if "fast"/"high speed" wording describes the rider, not another vehicle."""
    for m in _FAST.finditer(t):
        before = t[max(0, m.start() - 40):m.start()]
        last_vehicle = max((v.end() for v in _VEH.finditer(before)), default=-1)
        last_rider = max((b.end() for b in _RIDER.finditer(before)), default=-1)
        if last_vehicle < 0 or last_rider > last_vehicle:
            return True
    return False


def ebike_type(text):
    """Return "regular e-bike", "likely e-moto" or "unclear" for one e-bike narrative.

    Order: (1) "dirt bike or e-bike" style wording -> unclear; (2) e-moto words -> likely e-moto;
    (3) dirt-bike helmet or "motorcyclist" -> unclear; (4) "motorized bike" wording -> unclear
    at any speed (unless the story equates it with an e-bike); (5) the rider's stated speed
    decides (above 28 mph -> likely e-moto, unless downhill or someone else's guess; a range
    crossing 28 -> unclear); (6) "fast" with no speed -> unclear; (7) otherwise regular e-bike."""
    t = _story(text)
    if _EITHER.search(t):
        return "unclear"
    if _EMOTO.search(_GEAR.sub(" ", t)):
        return "likely e-moto"
    if _GEAR.search(t) or _UNCLEAR_EARLY.search(t):
        return "unclear"
    if _UNCLEAR.search(t) and not _SAME_AS_EBIKE.search(t):
        return "unclear"
    sp = rider_speeds(t)
    if sp:
        lo = max(s[0] for s in sp); hi = max(s[1] for s in sp)
        if lo > LIMIT_MPH:
            return "unclear" if (_DOWNHILL.search(t) or _GUESS.search(t)) else "likely e-moto"
        if hi > LIMIT_MPH:
            return "unclear"
    if not sp and _rider_fast(t):
        return "unclear"
    return "regular e-bike"


def add_ebike_type(df, text_col="Narrative"):
    """Add an ``ebike_type`` column for rows labelled "E-bike" (other rows get None)."""
    out = df.copy()
    eb = out["device"] == "E-bike"
    out["ebike_type"] = None
    out.loc[eb, "ebike_type"] = out.loc[eb, text_col].map(ebike_type)
    return out
