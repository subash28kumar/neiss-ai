"""Draw the fresh development (360) and test (240) samples for the e-bike/e-moto rule, v2.

Deterministic: stories are ranked by SHA-1 of "neissai-ebike-v2|<story id>" (no random seed) and
taken in that order within each sampling group. Groups use the locked v1.4 rule so weights can be
computed for all e-bike stories; stories in any earlier validation set are excluded.

    python validation/ebike_type_v2/sample.py
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
from neissai.ebike_type import ebike_type  # noqa: E402
from neissai.learn import norm_text, story_id  # noqa: E402

OLD = ["ebike_type_dev1_200.csv", "ebike_type_dev2_120.csv", "ebike_type_TEST_240.csv", "injurycoder_test_300.csv"]
CLUE = re.compile(r"\b(?:\d{2,3}\s*MPH|MOTORI[SZ]ED|THROTTLE|GAS|DIRT\s*BIKE|FAST|SPEED)")
TEST = {"likely e-moto": 25, "unclear": 75, "regular with clue words": 60, "regular": 80}
DEV = {"likely e-moto": 12, "unclear": 120, "regular with clue words": 120, "regular": 108}


def group(text: str) -> str:
    g = ebike_type(text)
    if g == "regular e-bike":
        return "regular with clue words" if CLUE.search(norm_text(text)) else "regular"
    return g


def rank(sid: str) -> str:
    return hashlib.sha1(("neissai-ebike-v2|" + sid).encode()).hexdigest()


def main():
    R = json.loads((ROOT / "docs/data/records.json").read_text())
    S = json.loads((ROOT / "docs/data/stories.json").read_text())
    eb = R["devices"].index("E-bike")
    used = set()
    for f in OLD:
        with open(ROOT / "validation" / f, newline="") as fh:
            used |= {story_id(r["narrative"]) for r in csv.DictReader(fh)}
    pop, pool, seen = {}, {}, set()
    for i, d in enumerate(R["d"]):
        if d != eb:
            continue
        t = S[i]
        g = group(t)
        pop[g] = pop.get(g, 0) + 1          # population counts (all e-bike stories) for weights
        sid = story_id(t)
        if sid in used or sid in seen:
            continue
        seen.add(sid)
        pool.setdefault(g, []).append({"id": sid, "year": R["years"][R["y"][i]], "narrative": norm_text(t), "stratum": g})
    test, dev = [], []
    for g in sorted(pool):
        rows = sorted(pool[g], key=lambda r: rank(r["id"]))
        test += rows[:TEST[g]]
        dev += rows[TEST[g]:TEST[g] + DEV[g]]
    for name, rows in (("test2_240_stories.csv", test), ("dev3_360_stories.csv", dev)):
        with open(HERE / name, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["id", "year", "stratum", "narrative"])
            w.writeheader(); w.writerows(sorted(rows, key=lambda r: rank(r["id"])))
    (HERE / "population.json").write_text(json.dumps({"all_ebike_stories": sum(pop.values()), "by_group": dict(sorted(pop.items()))}, indent=1) + "\n")
    print("test", len(test), "dev", len(dev), "population", dict(sorted(pop.items())))


if __name__ == "__main__":
    main()
