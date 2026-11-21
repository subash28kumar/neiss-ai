"""PROTOTYPE clean-up step for outside (non-NEISS) notes, tested in the stress test only.
Not used by NEISS-AI's published numbers. Turns common spellings and small typos into the words
the rules already know, before the rules read the note."""
from __future__ import annotations

import re

SPELL = [
    (r"\bELEC(?:T|TR)?\.? (BIKE|BICYCLE|SCOOTER)", r"ELECTRIC \1"),
    (r"\bELECTRONIC (BIKE|BICYCLE|SCOOTER)", r"ELECTRIC \1"),
    (r"\bBATTERY[- ]?(?:OPERATED |POWERED )?(BIKE|BICYCLE)\b", r"ELECTRIC \1"),
    (r"\bMI ?/ ?HR\b|\bMI/H\b|\bMILES/HR\b|\bM\.P\.H\.?", "MPH"),
    (r"\b(?:IMPRESSION|ASSESSMENT|DIAGNOSES)\s*:", "DX:"),
]
VOCAB = ["ELECTRIC", "BICYCLE", "SCOOTER", "HELMET", "HELMETED", "MOTORIZED", "VEHICLE", "MOTORCYCLE",
         "BIKE", "EBIKE", "ESCOOTER", "HOVERBOARD", "SKATEBOARD", "WITHOUT", "WEARING", "STRUCK", "MOPED"]


def _close(a, b):
    """True when a and b differ by one swap, one dropped letter or one extra letter."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        d = [i for i in range(len(a)) if a[i] != b[i]]
        return len(d) == 2 and d[1] == d[0] + 1 and a[d[0]] == b[d[1]] and a[d[1]] == b[d[0]]
    s, l = (a, b) if len(a) < len(b) else (b, a)
    return any(l[:i] + l[i + 1:] == s for i in range(len(l)))


def _fix(m):
    w = m.group(0)
    if len(w) < 5 or w in VOCAB:
        return w
    for v in VOCAB:
        if _close(w, v):
            return v
    return w


def cleanup(text: str) -> str:
    t = (text or "").upper()
    t = re.sub(r"[A-Z]{4,}", _fix, t)
    t = re.sub(r"\bE[- ]?BIKE\b", "E-BIKE", t)
    for p, r in SPELL:
        t = re.sub(p, r, t)
    return t
