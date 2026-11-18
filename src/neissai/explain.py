"""Explain how NEISS-AI read one e-bike injury story (for the website's "How it reads a story").

Every explanation is produced by the same rules and model weights the tool uses, and each
label is checked against the tool's own functions (``ebike_type``, ``helmet``,
``motor_vehicle`` and the classifier), so the page can never show reasoning the tool did not
use. Spans are (start, end) character positions in the story text, for highlighting.
"""
from __future__ import annotations

import importlib
import math
import re


# Package attributes of the same name are functions, so load the modules themselves.
C = importlib.import_module(".circumstances", __package__)
E = importlib.import_module(".ebike_type", __package__)
from .classifier import EbikeMopedClassifier, _features
from .devices import E_WORDS, _noncapturing

_EWORDS = re.compile(_noncapturing(E_WORDS))


def _spans(pattern, text, exclude=()):
    out = []
    for m in pattern.finditer(text):
        s, e = m.span()
        while s < e and text[s].isspace():
            s += 1
        while e > s and text[e - 1].isspace():
            e -= 1
        if e > s and not any(s < xe and xs < e for xs, xe in exclude):
            out.append([s, e])
    return out


def classifier_terms(clf: EbikeMopedClassifier, text: str, top: int = 6):
    """Probability of e-bike and the words that pushed the decision most (signed contributions)."""
    feats = _features(text, clf.ngram_max)
    w = {}
    for term, tf in feats.items():
        idf = clf.idf.get(term)
        if idf is not None:
            w[term] = (1.0 + math.log(tf) if clf.sublinear_tf else float(tf)) * idf
    norm = math.sqrt(sum(v * v for v in w.values())) or 1.0
    contrib = {t: v / norm * clf.coef.get(t, 0.0) for t, v in w.items()}
    z = clf.intercept + sum(contrib.values())
    p = 1.0 / (1.0 + math.exp(-z))
    terms = sorted((c for c in contrib.items() if abs(c[1]) > 1e-9), key=lambda c: -abs(c[1]))[:top]
    return p, [{"term": t, "weight": round(c, 3)} for t, c in terms]


def explain_device(text: str, year: int, clf: EbikeMopedClassifier):
    sp = _spans(_EWORDS, text)
    if sp:
        return {"label": "E-bike", "how": "words", "spans": sp,
                "why": "The story names an e-bike: " + ", ".join(f"“{text[s:e]}”" for s, e in sp[:2]) + "."}
    if year >= 2024:
        return {"label": "E-bike", "how": "code", "spans": [],
                "why": "CPSC's own e-bike product code (5045), used from 2024 on."}
    p, terms = classifier_terms(clf, text)
    return {"label": "E-bike" if p >= 0.5 else "Moped / minibike", "how": "classifier", "spans": [],
            "p": round(p, 3), "terms": terms,
            "why": (f"Before 2024, CPSC coded e-bikes and mopeds together (code 3215), and this story does not "
                    f"say which. The text classifier weighed the words and gave {round(p * 100)}% e-bike.")}


def explain_ebike_type(text: str):
    t = E._story(text)
    label = E.ebike_type(text)
    gear = _spans(E._GEAR, t)
    r = None
    if E._EITHER.search(t):
        r = ("unclear", "The story could mean either vehicle", _spans(E._EITHER, t))
    elif E._EMOTO.search(E._GEAR.sub(" ", t)):
        r = ("likely e-moto", "The story uses e-moto wording", _spans(E._EMOTO, t, exclude=gear))
    elif gear or E._UNCLEAR_EARLY.search(t):
        r = ("unclear", "The wording could mean a motorcycle", gear or _spans(E._UNCLEAR_EARLY, t))
    else:
        speeds = E.rider_speeds(t)
        sspans = []
        for m in E._SPEED.finditer(t):
            before = t[max(0, m.start() - 45):m.start()]
            lv = max((v.end() for v in E._VEH.finditer(before)), default=-1)
            lr = max((b.end() for b in E._RIDER.finditer(before)), default=-1)
            if lv < 0 or lr > lv:
                sspans.append(list(m.span()))
        if speeds:
            lo = max(s[0] for s in speeds); hi = max(s[1] for s in speeds)
            if lo > E.LIMIT_MPH:
                if E._DOWNHILL.search(t):
                    r = ("unclear", f"The rider's speed ({lo} mph) is above 28 mph, but going downhill", sspans)
                else:
                    r = ("likely e-moto", f"The rider's speed ({lo} mph) is above 28 mph, the top assisted speed "
                         "of a legal Class 3 e-bike", sspans)
            elif hi > E.LIMIT_MPH:
                r = ("unclear", f"The speed range ({lo}–{hi} mph) crosses 28 mph", sspans)
        if r is None and E._UNCLEAR.search(t) and not E._SAME_AS_EBIKE.search(t):
            r = ("unclear", "“Motorized bike” wording could mean either", _spans(E._UNCLEAR, t))
        if r is None and not speeds and E._FAST.search(t):
            r = ("unclear", "The story says it was fast but gives no speed", _spans(E._FAST, t))
        if r is None:
            if speeds:
                r = ("regular e-bike", f"The rider's speed ({max(s[1] for s in speeds)} mph) is within legal "
                     "e-bike speeds, and there are no e-moto words", sspans)
            else:
                r = ("regular e-bike", "No e-moto words and no rider speed above 28 mph", [])
    if r[0] != label:  # never show reasoning that disagrees with the tool
        r = (label, "", [])
    return {"label": label, "why": (r[1] + ".") if r[1] else "", "spans": r[2]}


def explain_helmet(text: str):
    t = text.upper()
    label = C.helmet(text)
    if "HELMET" not in t:
        return {"label": label, "why": "The story does not mention a helmet.", "spans": []}
    if C.UNK.search(t):
        return {"label": label, "why": "The story says helmet use is unknown.", "spans": _spans(C.UNK, t)}
    no = _spans(C.NO, t)
    yes = _spans(C.YES, t, exclude=no)
    if label == "no":
        return {"label": label, "why": "The story says no helmet was worn.", "spans": no}
    if label == "yes":
        return {"label": label, "why": "The story says a helmet was worn.", "spans": yes}
    return {"label": label, "why": "The story mentions a helmet but does not say clearly whether it was worn.",
            "spans": no + yes}


def explain_motor_vehicle(text: str):
    t = text.upper()
    label = C.motor_vehicle(text)
    if not label:
        return {"label": False, "why": "The story does not describe contact with a motor vehicle.", "spans": []}
    load = _spans(C.LOADING, t)
    return {"label": True, "why": "The story describes contact with a motor vehicle.",
            "spans": _spans(C.MV, t, exclude=load)}


def explain_story(text: str, year: int, clf: EbikeMopedClassifier | None = None) -> dict:
    clf = clf or EbikeMopedClassifier.load_default()
    return {"text": text, "year": year,
            "device": explain_device(text, year, clf),
            "type": explain_ebike_type(text),
            "helmet": explain_helmet(text),
            "mv": explain_motor_vehicle(text)}
