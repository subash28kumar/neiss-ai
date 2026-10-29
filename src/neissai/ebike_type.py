"""E-bike or e-moto? A rule that reads NEISS e-bike narratives (added after v1.4).

Some vehicles counted as "e-bikes" are really electric motorcycles ("e-motos", such as
Sur-Ron or Talaria models) or e-bikes ridden far above legal e-bike speeds. NEISS has no code
for this, and the stated e-bike class (1, 2 or 3) almost never appears in the narrative, so the
rule uses only what the story says:

* ``"likely e-moto"``  - e-moto wording (SUR-RON, TALARIA, E-MOTO, electric motorcycle or
  dirt bike, gas- or engine-powered), or the rider's own speed above 28 mph (the top assisted
  speed of a legal Class 3 e-bike), not going downhill.
* ``"unclear"``        - wording that could mean either ("motorized bike", "motor bike",
  "dirt bike or e-bike", "motorcyclist", a dirt-bike helmet), a speed range that crosses
  28 mph, a downhill speed above 28 mph, or "fast"/"high speed" with no speed given.
* ``"regular e-bike"`` - everything else.

Only the story before the diagnosis ("DX") is read, because diagnosis coding phrases such as
"FALL FROM MOTORIZED BIKE" describe a coding category, not the vehicle. Speeds that belong to
another vehicle or rider ("STRUCK BY A CAR GOING 30 MPH") are ignored.

Test: built on 320 stories, then locked and tested once on 240 new stories (2019-2025)
labelled blind: 98.4% in the right group across all e-bike stories (95% CI 97.2-99.5%); likely
e-moto share 2.0% by the rule vs 2.0% by the reviewers; single "likely e-moto" calls are right
about 3 times in 4. See validation/EBIKE_TYPE.md. A narrative names an e-moto only when the
writer says so, so "likely e-moto" is a lower bound, not a full count.
"""
from __future__ import annotations

import re

import pandas as pd

LIMIT_MPH = 28
_EMOTO = re.compile(r"SUR-?RON|TALARIA|\bE-?MOTO|ELEC\w* (?:MOTORCYCLE|DIRT ?BIKE)|DIRT ?BIKE|GAS[- ]?(?:POWERED|MOTORIZED)"
                    r"|ENGINE[- ]?(?:POWERED|MOTORIZED|BIKE|BICYCLE)|(?:MOTORIZED|GAS)\W+(?:\w+\W+){0,2}ENGINE")
_EITHER = re.compile(r"DIRT ?BIKE,? OR|\bOR (?:AN? )?DIRT ?BIKE|MOTORCYCLE,? OR (?:AN? )?E-?BIKE|E-?BIKE,? OR (?:AN? )?MOTORCYCLE")
_GEAR = re.compile(r"DIRT ?BIKE\W{0,2} ?HELMET")
_VEH = re.compile(r"(?<!PARKED )\b(?:CAR|VEHICLE|AUTO|TRUCK|SUV|VAN|BUS|DRIVER|MOTORIST|MOTORCYCLE|MOPED)\b"
                  r"|\b(?:ANOTHER|OTHER) (?:E-?BIKE|BIKE|BICYCLE|BICYCLIST|CYCLIST|RIDER|SCOOTER|E-?SCOOTER)")
_RIDER = re.compile(r"BIKE|BICYCLE|RIDING|RIDER|\bPT\b|PATIENT")
_SPEED = re.compile(r"(\d{1,3})(?: ?(?:-|TO|OR) ?(\d{1,3}))? ?(?:MPH|MILES PER HOUR|MILES AN HOUR)")
_UNCLEAR_EARLY = re.compile(r"MOTORCYCLIST|MOBILITY SCOOTER")
_UNCLEAR = re.compile(r"MOTORI[ZS]ED +(?:BIKE|BICYCLE|\*)|MOTOR ?BIKE|MOTOR BICYCLE")
_SAME_AS_EBIKE = re.compile(r"MOTORI[ZS]ED +(?:BIKE|BICYCLE) ?(?:/|\(|,|OR|AKA) ?(?:AN? )?(?:E-?BIKE|ELECTRIC)")
_FAST = re.compile(r"\bFAST\b|HIGH SPEED|SPEEDING")
_DOWNHILL = re.compile(r"DOWN ?HILL|DOWN A HILL|DOWN THE HILL")
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
        before = t[max(0, m.start() - 45):m.start()]
        last_vehicle = max((v.end() for v in _VEH.finditer(before)), default=-1)
        last_rider = max((b.end() for b in _RIDER.finditer(before)), default=-1)
        if last_vehicle < 0 or last_rider > last_vehicle:
            out.append((lo, hi))
    return out


def ebike_type(text):
    """Return "regular e-bike", "likely e-moto" or "unclear" for one e-bike narrative.

    Order: (1) "dirt bike or e-bike" style wording -> unclear; (2) e-moto words -> likely e-moto;
    (3) dirt-bike helmet or "motorcyclist" -> unclear; (4) the rider's stated speed decides
    (above 28 mph -> likely e-moto, unless downhill; a range crossing 28 -> unclear);
    (5) "motorized bike" wording -> unclear at any speed (unless the story equates it with an
    e-bike); (6) "fast" with no speed -> unclear; (7) otherwise regular e-bike."""
    t = _story(text)
    if _EITHER.search(t):
        return "unclear"
    if _EMOTO.search(_GEAR.sub(" ", t)):
        return "likely e-moto"
    if _GEAR.search(t) or _UNCLEAR_EARLY.search(t):
        return "unclear"
    sp = rider_speeds(t)
    if sp:
        lo = max(s[0] for s in sp); hi = max(s[1] for s in sp)
        if lo > LIMIT_MPH:
            return "unclear" if _DOWNHILL.search(t) else "likely e-moto"
        if hi > LIMIT_MPH:
            return "unclear"
    if _UNCLEAR.search(t) and not _SAME_AS_EBIKE.search(t):
        return "unclear"
    if not sp and _FAST.search(t):
        return "unclear"
    return "regular e-bike"


def add_ebike_type(df, text_col="Narrative"):
    """Add an ``ebike_type`` column for rows labelled "E-bike" (other rows get None)."""
    out = df.copy()
    eb = out["device"] == "E-bike"
    out["ebike_type"] = None
    out.loc[eb, "ebike_type"] = out.loc[eb, text_col].map(ebike_type)
    return out
