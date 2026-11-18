"""The story explainer must always agree with the tool's own labels."""
import csv
from pathlib import Path

import neissai
from neissai.explain import explain_story, classifier_terms
from neissai.classifier import EbikeMopedClassifier

VAL = Path(__file__).resolve().parents[1] / "validation"
_E = __import__("importlib").import_module("neissai.ebike_type")
_C = __import__("importlib").import_module("neissai.circumstances")


def _rows(name, col="narrative"):
    with open(VAL / name, newline="") as f:
        return [r[col] for r in csv.DictReader(f)]


def test_labels_match_tool_on_test_sets():
    clf = EbikeMopedClassifier.load_default()
    texts = _rows("ebike_type_TEST_240.csv") + _rows("injurycoder_test_300.csv")
    for t in texts:
        t = t.upper()
        x = explain_story(t, 2025, clf)
        assert x["type"]["label"] == _E.ebike_type(t)
        assert x["helmet"]["label"] == _C.helmet(t)
        assert x["mv"]["label"] == _C.motor_vehicle(t)
        for part in ("device", "type", "helmet", "mv"):
            for s, e in x[part]["spans"]:
                assert 0 <= s < e <= len(t) and not t[s].isspace() and not t[e - 1].isspace()


def test_classifier_terms_match_probability():
    clf = EbikeMopedClassifier.load_default()
    for t in ["83YOM FELL OFF ELECTIC BICYCLE AND HIT HEAD. DX: CHI", "45YOM FELL OFF MOPED DX FX"]:
        p, terms = classifier_terms(clf, t)
        assert abs(p - float(clf.predict_proba([t])[0])) < 1e-9
        assert terms and all("term" in x and "weight" in x for x in terms)
