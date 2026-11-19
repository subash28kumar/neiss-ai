"""Guardrails and determinism of learning from human labels (neissai.learn)."""
import csv
import json
from pathlib import Path

import pandas as pd

from neissai import learn as L

ROOT = Path(__file__).resolve().parents[1]
LD = ROOT / "validation" / "learning"

SPOT = {"sp1": {"mv": "no", "helmet": "yes", "etype": "regular e-bike"},
        "sp2": {"mv": "yes", "helmet": "no", "etype": "regular e-bike"},
        "sp3": {"mv": "no", "helmet": "not mentioned", "etype": "regular e-bike"},
        "sp4": {"mv": "yes", "helmet": "yes", "etype": "regular e-bike"},
        "sp5": {"mv": "no", "helmet": "no", "etype": "regular e-bike"}}
ITEMS = {"h1": "25YOM ON E-BIKE GOING ABOUT 30 MPH FELL. DX: ABRASION",
         "h2": "30YOF ON MOTORIZED BIKE SWERVED TO AVOID CAR AND FELL DX: FX WRIST",
         **{k: "SPOT STORY " + k for k in SPOT}}


def person(name, org, answers, spot_right=True):
    rows = []
    for sid, a in SPOT.items():
        b = dict(a) if spot_right else {"mv": "yes" if a["mv"] == "no" else "no", "helmet": "no", "etype": "unclear"}
        rows.append({"set": "C", "id": sid, "labeler": name, "organization": org, **b, "file": name})
    for sid, a in answers.items():
        rows.append({"set": "C", "id": sid, "labeler": name, "organization": org,
                     **{q: a.get(q, "") for q in L.QUESTIONS}, "file": name})
    return rows


TRUSTED = {L._who("Ann", "Uni A"), L._who("Bob", "Uni B"), L._who("Cat", "Uni C")}
H1 = {"h1": {"mv": "no", "helmet": "not mentioned", "etype": "unclear"}}


def test_two_trusted_people_agreeing_are_learned():
    rows = person("Ann", "Uni A", H1) + person("Bob", "Uni B", H1)
    mem, rep = L.build_memory(rows, ITEMS, SPOT, TRUSTED, set())
    assert mem["h1"]["etype"] == "unclear" and mem["h1"]["etype_votes"] == "2/2"
    assert "sp1" not in mem  # spot checks test people; they are never learned


def test_one_person_is_not_enough():
    mem, rep = L.build_memory(person("Ann", "Uni A", H1), ITEMS, SPOT, TRUSTED, set())
    assert mem == {} and rep["skipped"]["only one person"] == 3


def test_untrusted_reviewer_is_ignored():
    rows = person("Ann", "Uni A", H1) + person("Mallory", "Nowhere", H1)
    mem, rep = L.build_memory(rows, ITEMS, SPOT, TRUSTED, set())
    assert mem == {}
    assert rep["labellers"][L._who("Mallory", "Nowhere")]["used"] is False


def test_failing_spot_checks_excludes_a_reviewer():
    rows = person("Ann", "Uni A", H1) + person("Bob", "Uni B", H1, spot_right=False)
    mem, rep = L.build_memory(rows, ITEMS, SPOT, TRUSTED, set())
    assert mem == {}
    assert "spot checks" in rep["labellers"][L._who("Bob", "Uni B")]["reason"]


def test_disagreement_is_not_learned():
    other = {"h1": {"mv": "yes", "helmet": "yes", "etype": "likely e-moto"}}
    rows = person("Ann", "Uni A", H1) + person("Bob", "Uni B", other)
    mem, rep = L.build_memory(rows, ITEMS, SPOT, TRUSTED, set())
    assert mem == {} and rep["skipped"]["people did not agree"] == 3


def test_majority_needs_three_quarters():
    other = {"h1": {"etype": "likely e-moto"}}
    rows = person("Ann", "Uni A", H1) + person("Bob", "Uni B", H1) + person("Cat", "Uni C", other)
    mem, _ = L.build_memory(rows, ITEMS, SPOT, TRUSTED, set())
    assert "etype" not in mem.get("h1", {})  # 2 of 3 = 67% < 75%
    assert mem["h1"]["mv"] == "no"           # mv: 2 of 2 answered agree


def test_locked_test_stories_are_never_learned():
    rows = person("Ann", "Uni A", H1) + person("Bob", "Uni B", H1)
    mem, rep = L.build_memory(rows, ITEMS, SPOT, TRUSTED, {"h1"})
    assert mem == {} and rep["skipped"]["locked test story"] == 2


def test_deterministic():
    rows = person("Bob", "Uni B", H1) + person("Ann", "Uni A", H1)
    a = L.build_memory(rows, ITEMS, SPOT, TRUSTED, set())
    b = L.build_memory(list(reversed(rows)), ITEMS, SPOT, TRUSTED, set())
    assert json.dumps(a[0], sort_keys=True) == json.dumps(b[0], sort_keys=True)


def test_memory_exact_and_closest_match():
    m = L.HumanMemory([{"id": L.story_id(ITEMS["h1"]), "text": L.norm_text(ITEMS["h1"]), "etype": "unclear"}])
    hit = m.lookup(ITEMS["h1"].lower(), "etype")
    assert hit["source"] == "human" and hit["label"] == "unclear"
    near = m.lookup("25YOM ON E-BIKE GOING ABOUT 30 MPH FELL.  DX: ABRASIONS", "etype")
    assert near["source"] == "closest human match" and near["similarity"] >= L.CLOSE
    assert m.lookup("70YOF FELL OFF E-BIKE IN DRIVEWAY DX: HIP FX", "etype") is None
    assert m.lookup(ITEMS["h1"], "mv") is None  # memory has no mv answer for it
    assert m.lookup_many([ITEMS["h1"], "70YOF FELL OFF E-BIKE IN DRIVEWAY DX: HIP FX"], "etype")[1] is None


def test_empty_memory_changes_nothing():
    df = pd.DataFrame({"Narrative": ["A"], "motor_vehicle": [1], "helmet_status": ["no"], "ebike_type": ["unclear"]})
    out = L.apply_human_memory(df, L.HumanMemory([]))
    assert out.equals(df)


def test_apply_memory_overrides_rule_answers():
    t = ITEMS["h1"]
    m = L.HumanMemory([{"id": L.story_id(t), "text": L.norm_text(t), "etype": "unclear", "mv": "no"}])
    df = pd.DataFrame({"Narrative": [t, "OTHER STORY"], "motor_vehicle": [1, 1], "helmet_status": ["no", "no"],
                       "helmet_no": [1, 1], "helmet_yes": [0, 0], "ebike_type": ["likely e-moto", None]})
    out = L.apply_human_memory(df, m)
    assert out.loc[0, "ebike_type"] == "unclear" and out.loc[0, "ebike_type_source"] == "human"
    assert out.loc[0, "motor_vehicle"] == 0 and out.loc[1, "motor_vehicle"] == 1
    assert pd.isna(out.loc[1, "ebike_type"])


def test_set_c_has_no_locked_stories_and_valid_spot_checks():
    locked = L.locked_ids()
    items = list(csv.DictReader(open(LD / "set_c_items.csv", newline="")))
    assert len(items) >= 200 and not any(r["id"] in locked for r in items)
    assert all(L.story_id(r["text"]) == r["id"] for r in items)
    spot = list(csv.DictReader(open(LD / "set_c_spotcheck.csv", newline="")))
    assert len(spot) >= L.SPOT_MIN and all(r[q] in L.VALUES[q] for r in spot for q in L.QUESTIONS)
    ids = {r["id"] for r in items}
    assert all(r["id"] in ids for r in spot)


def test_ebike_rule_matches_locked_fingerprint():
    """The e-moto rule code must not change after its fresh test without a new test."""
    import hashlib
    s = (ROOT / "src" / "neissai" / "ebike_type.py").read_text()
    h = hashlib.sha256(s[s.index("from __future__"):].encode()).hexdigest()
    assert h in (LD.parent / "ebike_type_v2" / "LOCK.txt").read_text()
