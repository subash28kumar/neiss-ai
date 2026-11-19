"""Learning from people: turn trusted human labels into a "human memory" NEISS-AI can use.

How it works (all steps are deterministic: same inputs -> same outputs, no randomness):

1. People label stories on docs/label.html (Set C, "Help train") and email the CSV.
2. ``build_memory`` applies the guardrails below and keeps only labels people agree on.
3. ``HumanMemory.lookup`` answers a story from that memory:
   * the same story (exact text match)  -> the people's answer, source "human";
   * a near-identical story (closest match, cosine similarity >= ``CLOSE``) -> the answer of the
     closest labelled story, source "closest human match";
   * otherwise nothing, and NEISS-AI's own rules answer as before.
4. A new memory only goes live if ``validation/check_learning.py`` shows no drop in accuracy on
   the locked test sets (stories that are never learned from).

Guardrails against careless or bad answers:

* Trusted labellers only: a CSV counts only if its labeller is listed in
  ``validation/learning/trusted_labellers.csv`` with ``approved`` = yes.
* Spot checks: Set C mixes in stories with known answers. A labeller who answers fewer than 5 of
  them, or gets under 90% right, is left out entirely.
* Agreement: an answer is learned only when at least 2 trusted labellers give it and at least
  75% of the trusted answers for that story and question agree.
* Locked tests: stories in the validation test and development sets are never learned from.
* No automatic updates: memory is rebuilt by hand, reviewed, and every version is kept in git.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

QUESTIONS = ("mv", "helmet", "etype")
VALUES = {
    "mv": {"yes", "no"},
    "helmet": {"yes", "no", "not mentioned"},
    "etype": {"regular e-bike", "likely e-moto", "unclear"},
}
MIN_AGREE = 2          # at least this many trusted people must give the same answer
MIN_SHARE = 0.75       # ...and they must be at least this share of the trusted answers
SPOT_MIN = 5           # a labeller must answer at least this many spot-check stories
SPOT_PASS = 0.90       # ...and get at least this share of spot-check answers right
CLOSE = 0.90           # closest-match similarity needed to reuse a human answer

ROOT = Path(__file__).resolve().parents[2]
VAL = ROOT / "validation"
LOCKED_FILES = ("ebike_type_TEST_240.csv", "ebike_type_dev1_200.csv", "ebike_type_dev2_120.csv",
                "injurycoder_test_300.csv")


def norm_text(text: str) -> str:
    """Upper-case and collapse spaces, so the same story always gives the same id."""
    return " ".join(str(text or "").upper().split())


def story_id(text: str) -> str:
    """Stable id for a story: the first 12 hex digits of the SHA-1 of its normalised text."""
    return "s" + hashlib.sha1(norm_text(text).encode("utf-8")).hexdigest()[:12]


def locked_ids(val_dir: Path = VAL) -> set[str]:
    """Ids of every story in the locked validation sets; these are never learned from."""
    out = set()
    for name in LOCKED_FILES:
        p = Path(val_dir) / name
        if not p.exists():
            continue
        with open(p, newline="") as f:
            for r in csv.DictReader(f):
                out.add(story_id(r["narrative"]))
    return out


def _clean(v) -> str:
    v = str(v or "").strip().lower()
    return {"true": "yes", "false": "no", "worn": "yes", "not worn": "no"}.get(v, v)


def read_label_csvs(paths: Iterable[Path]) -> list[dict]:
    """Read CSVs exported by docs/label.html. Rows from every file are returned in a fixed order."""
    rows = []
    for p in sorted(Path(x) for x in paths):
        with open(p, newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                rows.append({
                    "set": (r.get("set") or "").strip().upper(),
                    "id": (r.get("case_number") or "").strip(),
                    "labeler": " ".join((r.get("labeler") or "").split()),
                    "organization": " ".join((r.get("organization") or "").split()),
                    **{q: _clean(r.get(q)) for q in QUESTIONS},
                    "file": p.name,
                })
    return rows


def read_trusted(path: Path) -> set[str]:
    """Approved labellers, matched on name and organization (case-insensitive)."""
    out = set()
    if not Path(path).exists():
        return out
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if (r.get("approved") or "").strip().lower() in {"yes", "y", "true", "1"}:
                out.add(_who(r.get("name"), r.get("organization")))
    return out


def _who(name, org) -> str:
    return (" ".join(str(name or "").split()) + " | " + " ".join(str(org or "").split())).lower()


def build_memory(rows: list[dict], items: dict[str, str], spot_key: dict[str, dict],
                 trusted: set[str], locked: set[str]) -> tuple[dict, dict]:
    """Apply the guardrails and return (memory, report).

    rows      -- label rows from ``read_label_csvs`` (only set "C" rows are used)
    items     -- story id -> story text for Set C
    spot_key  -- story id -> known answers for the spot-check stories
    trusted   -- approved labellers from ``read_trusted``
    locked    -- story ids that must never be learned from
    """
    report = {"labellers": {}, "learned": 0, "skipped": Counter()}
    by_person = defaultdict(list)
    for r in rows:
        if r["set"] != "C":
            report["skipped"]["not Set C"] += 1
            continue
        by_person[_who(r["labeler"], r["organization"])].append(r)

    good_people = []
    for who in sorted(by_person):
        rs = by_person[who]
        info = {"rows": len(rs), "trusted": who in trusted}
        right = total = 0
        for r in rs:
            key = spot_key.get(r["id"])
            if not key:
                continue
            for q in QUESTIONS:
                if q in key and r[q]:
                    total += 1
                    right += r[q] == key[q]
        info["spot_checks"] = total
        info["spot_right"] = right
        info["spot_share"] = round(right / total, 3) if total else None
        passed = total >= SPOT_MIN and right / total >= SPOT_PASS
        info["used"] = info["trusted"] and passed
        info["reason"] = ("used" if info["used"] else "not on the trusted list" if not info["trusted"]
                          else f"spot checks: {right} of {total} right (needs {SPOT_MIN}+ answered, {SPOT_PASS:.0%}+ right)")
        report["labellers"][who] = info
        if info["used"]:
            good_people.append(who)

    votes = defaultdict(Counter)            # (story id, question) -> Counter(answer)
    for who in good_people:
        seen = {}
        for r in by_person[who]:
            seen[r["id"]] = r                # a person's last row for a story wins
        for sid, r in seen.items():
            if sid in spot_key:
                continue                     # spot checks test people; they are not learned
            if sid in locked:
                report["skipped"]["locked test story"] += 1
                continue
            if sid not in items:
                report["skipped"]["unknown story id"] += 1
                continue
            for q in QUESTIONS:
                if r[q] in VALUES[q]:
                    votes[(sid, q)][r[q]] += 1

    memory = {}
    for (sid, q) in sorted(votes):
        c = votes[(sid, q)]
        n = sum(c.values())
        top, k = sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        if k >= MIN_AGREE and k / n >= MIN_SHARE:
            m = memory.setdefault(sid, {"id": sid, "text": norm_text(items[sid])})
            m[q] = top
            m[q + "_votes"] = f"{k}/{n}"
        else:
            report["skipped"]["people did not agree" if n >= MIN_AGREE else "only one person"] += 1
    report["learned"] = sum(1 for m in memory.values() for q in QUESTIONS if q in m)
    report["stories"] = len(memory)
    report["skipped"] = dict(sorted(report["skipped"].items()))
    return memory, report


class HumanMemory:
    """Answers stories from trusted human labels: same story first, then the closest match."""

    def __init__(self, entries: list[dict] | None = None, close: float = CLOSE):
        self.entries = sorted(entries or [], key=lambda e: e["id"])
        self.close = close
        self.by_id = {e["id"]: e for e in self.entries}
        self._vec = self._mat = None
        if self.entries:
            from sklearn.feature_extraction.text import TfidfVectorizer
            self._vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), lowercase=False,
                                        sublinear_tf=True, dtype=float)
            self._mat = self._vec.fit_transform([e["text"] for e in self.entries])

    @classmethod
    def load(cls, path: Path | None = None) -> "HumanMemory":
        path = Path(path or VAL / "learning" / "human_memory.json")
        if not path.exists():
            return cls([])
        return cls(json.loads(path.read_text())["entries"])

    def __len__(self):
        return len(self.entries)

    def lookup(self, text: str, question: str) -> dict | None:
        """Return {"label", "source", "match_id", "similarity"} or None if memory cannot answer."""
        if not self.entries:
            return None
        sid = story_id(text)
        e = self.by_id.get(sid)
        if e and question in e:
            return {"label": e[question], "source": "human", "match_id": sid, "similarity": 1.0}
        sims = (self._mat @ self._vec.transform([norm_text(text)]).T).toarray().ravel()
        best = None
        for i in sorted(range(len(sims)), key=lambda j: (-sims[j], self.entries[j]["id"])):
            if sims[i] < self.close:
                break
            if question in self.entries[i]:
                best = i
                break
        if best is None:
            return None
        e = self.entries[best]
        return {"label": e[question], "source": "closest human match", "match_id": e["id"],
                "similarity": round(float(sims[best]), 3)}

    def lookup_many(self, texts: list[str], question: str) -> list[dict | None]:
        """Vectorised ``lookup`` for many stories (same answers, much faster)."""
        if not self.entries or not len(texts):
            return [None] * len(texts)
        have = [i for i, e in enumerate(self.entries) if question in e]
        if not have:
            return [None] * len(texts)
        sub = self._mat[have]
        out = []
        X = self._vec.transform([norm_text(t) for t in texts])
        S = (X @ sub.T).tocsr()
        for r, t in enumerate(texts):
            sid = story_id(t)
            e = self.by_id.get(sid)
            if e and question in e:
                out.append({"label": e[question], "source": "human", "match_id": sid, "similarity": 1.0})
                continue
            row = S.getrow(r)
            best = None
            for j, v in sorted(zip(row.indices, row.data), key=lambda kv: (-kv[1], self.entries[have[kv[0]]]["id"])):
                if v >= self.close:
                    best = (j, v)
                break
            if best is None:
                out.append(None)
            else:
                e = self.entries[have[best[0]]]
                out.append({"label": e[question], "source": "closest human match", "match_id": e["id"],
                            "similarity": round(float(best[1]), 3)})
        return out


def apply_human_memory(df, memory: HumanMemory | None = None, text_col: str = "Narrative"):
    """Let trusted human answers replace rule answers in a labelled NEISS table.

    Updates ``motor_vehicle``, ``helmet_status``/``helmet_yes``/``helmet_no`` and ``ebike_type``
    where memory has an answer, and adds ``*_source`` columns ("rule", "human" or
    "closest human match"). With an empty memory the table is returned unchanged.
    """
    memory = memory if memory is not None else HumanMemory.load()
    if not len(memory):
        return df
    out = df.copy()
    texts = out[text_col].fillna("").astype(str).tolist()
    if "motor_vehicle" in out:
        out["motor_vehicle_source"] = "rule"
        for i, hit in enumerate(memory.lookup_many(texts, "mv")):
            if hit:
                out.iat[i, out.columns.get_loc("motor_vehicle")] = int(hit["label"] == "yes")
                out.iat[i, out.columns.get_loc("motor_vehicle_source")] = hit["source"]
    if "helmet_status" in out:
        out["helmet_source"] = "rule"
        for i, hit in enumerate(memory.lookup_many(texts, "helmet")):
            if hit:
                out.iat[i, out.columns.get_loc("helmet_status")] = hit["label"]
                out.iat[i, out.columns.get_loc("helmet_source")] = hit["source"]
        out["helmet_no"] = (out["helmet_status"] == "no").astype(int)
        out["helmet_yes"] = (out["helmet_status"] == "yes").astype(int)
    if "ebike_type" in out:
        out["ebike_type_source"] = "rule"
        eb = out["ebike_type"].notna().tolist()
        idx = [i for i, ok in enumerate(eb) if ok]
        for i, hit in zip(idx, memory.lookup_many([texts[i] for i in idx], "etype")):
            if hit:
                out.iat[i, out.columns.get_loc("ebike_type")] = hit["label"]
                out.iat[i, out.columns.get_loc("ebike_type_source")] = hit["source"]
    return out
