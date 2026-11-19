# E-bike or e-moto? How the rule was built and tested

## Version 2 (November 2026) — current

The v1.4 rule (below) scored 99.5% on the stories it was built from but 94.6% raw on its test,
so it was rebuilt properly:

1. **Retired the old test.** The 240 v1.4 test stories had been looked at, so they became
   development data. Development set for v2: 200 + 120 + 240 old stories + **360 new stories**
   (`ebike_type_v2/ebike_type_dev3_360.csv`) = 920.
2. **New stories, drawn deterministically** (`ebike_type_v2/sample.py`; ranked by SHA-1, no random
   seed; none from any earlier set): 360 for development and **240 for a fresh test**
   (`ebike_type_v2/ebike_type_TEST2_240.csv`), sampled by group (25 likely e-moto, 75 unclear,
   60 regular with clue words, 80 regular) and weighted back to all 5,839 e-bike stories.
3. **Labelled blind** by two AI reviewers per story who saw only the written definitions
   (`ebike_type_v2/DEFINITIONS.md`, fixed before labelling) and never the rule; a third settled
   disagreements (dev 359/360 agreed, test 239/240). Same kind of AI system, so not as independent
   as two human readers; the outside human check (labelling page) remains the next step.
4. **Rule fixes, made on development stories only:** "motorized bike/bicycle" wording is unclear at
   any speed (as the definitions say); second-hand guessed speeds and downhill slopes/inclines are
   unclear; "bike vs e-bike" is unclear; a clutch means e-moto; "fast" or a speed that belongs to
   another vehicle is ignored; "motorized electric bicycle" and "e-bike/motorbike" are treated as
   e-bikes.
5. **Locked** (SHA-256 in `ebike_type_v2/LOCK.txt`; a test checks it), then **scored once** on the
   fresh test (`ebike_type_v2/evaluate.py` -> `ebike_type_v2/RESULTS.md`). The rule was not changed
   after the test; its 7 misses are listed there for the next version.

| Fresh test, 240 stories | v2 (new) | v1.4 (old) |
|---|---|---|
| Right group, weighted to all e-bike stories | **98.9%** (95% CI 97.9–99.7%) | 98.6% (97.5–99.4%) |
| Right group, raw | 233/240 (97.1%) | 229/240 (95.4%) |
| Likely e-moto precision / recall (weighted) | 95.2% / 100% | see RESULTS.md |
| Likely e-moto share: rule vs reviewers | 1.7% vs 1.6% | |

National estimates with v2, 2025: regular e-bike 94,300 (92.8%), unclear 5,700 (5.7%), likely
e-moto 1,600 (1.5%; 95% CI 800–2,300). Likely e-motos were 0.9–2.0% of e-bike visits in every
year 2019–2025.

---

## Version 1.4 (October 2026) — history

`neissai.ebike_type()` sorts each NEISS e-bike story into **regular e-bike**, **likely e-moto**
or **unclear** (rules in `src/neissai/ebike_type.py`; definitions in its docstring).

## Why a rule, and what it can't do
NEISS has no code for e-motos (electric motorcycles such as Sur-Ron or Talaria). CPSC blacks
out brand names in the stories ("***"), and the e-bike class (1, 2 or 3) was stated in 0 of
4,519 e-bike stories from 2023–2025. So the rule can only use what the story says: e-moto
wording, and the rider's stated speed (above 28 mph, the top assisted speed of a legal Class 3
e-bike). A story names an e-moto only when the writer says so, so **"likely e-moto" is a lower
bound**; an e-moto described only as an "e-bike" cannot be found.

## Steps
1. **Build set 1 (200 stories, 2023–2025)**: 100 with clues (speed above 20 mph, or motorized,
   throttle, gas, dirt bike, fast) and 100 random. Suggested labels with written reasons; every
   likely e-moto and unclear label was checked by the author. File: `ebike_type_dev1_200.csv`.
2. **Build set 2 (120 new stories, 2019–2025)**: labelled blind by two AI-assisted reviewers who
   never saw the rule (agreement 115/120, kappa 0.93); the 5 disagreements were settled using the
   author's set-1 decisions. Errors found here led to six fixes (ignore diagnosis coding phrases;
   ignore speeds of another bike or rider; read "20 to 30 mph" as a range; "dirt bike or e-bike"
   = unclear; "engine motorized bicycle" = likely e-moto; dirt-bike helmet = unclear).
   File: `ebike_type_dev2_120.csv`. After the fixes the rule agreed with 199/200 (set 1) and
   119/120 (set 2) — in-sample figures, not used as the accuracy claim.
3. **Rule locked** before the final test. SHA-256 of the rule code (everything in
   `ebike_type.py` from `from __future__` down; only the description text above it was edited
   after the test): `fec60989d1d1f6825596d92a523cc8bf6b33df5fa571369514fb9a6cb56927d2`.
4. **Final test (240 new stories, 2019–2025, none used before)**, sampled by the rule's group so
   rare groups are well covered: 40 likely e-moto, 60 unclear, 60 regular with clue words, 80
   regular without. Labelled blind against written definitions by two new AI-assisted
   reviewers who never saw the rule (a third would settle disagreements; none were needed: they
   agreed on all 240). Because both reviewers were the same kind of AI system, this agreement
   is not as independent as two human readers; a human second reader is planned before any
   journal paper. File: `ebike_type_TEST_240.csv`. The rule was not changed after the test.

## Final test results (the accuracy claim)
Results are weighted back to all 5,839 e-bike stories, 2019–2025, using the size of each
sampling group (regular without clues 4,031; regular with clues 1,154; unclear 537; likely e-moto 117).

| | Result |
|---|---|
| Stories in the right group (weighted) | **98.4%** (95% CI 97.2–99.5%; bootstrap within groups) |
| Share that are likely e-motos | rule 2.0% vs reviewers 2.0% |
| Share that are unclear | rule 9.2% vs reviewers 10.2% |
| Regular e-bike: precision / recall | 98.9% / 100% |
| Likely e-moto: precision / recall | 77.5% / 76.3% |
| Unclear: precision / recall | 98.3% / 89.1% |

Raw (unweighted) agreement on the 240: 227 (94.6%).

Of the 13 misses, 7 are "motorized bicycle/bike" stories with a rider speed over 28 mph: the
rule says likely e-moto, the written definitions said "motorized bike" is unclear at any speed.
Others: an engine "clutch" on a motorized bicycle (reviewers: e-moto; rule: unclear), a
"motorized street bike" doing a wheelie (reviewers: e-moto; rule: regular), "dirt bike versus
electric bike" (reviewers: unclear; rule: e-moto), a bystander's disputed 30 mph estimate, a
motorized bicycle with no speed (rule: regular, a typo "BICYLCE"), and "high rate of speed"
with no number.

**What this means.** The rule is reliable for the national share of likely e-motos (errors in
both directions cancel), and for separating regular e-bikes. Individual "likely e-moto" calls
are right about 3 times in 4, so do not use single records as proof that a vehicle was an e-moto.

## National estimates (all e-bike stories, 2019–2025)
2025: regular e-bike 94,500 (93.0%), unclear 5,300 (5.2%), likely e-moto 1,900 (1.8%; 95% CI
1,100–2,600). Likely e-motos were 1.8–2.7% of e-bike visits in every year 2019–2025.
Full table: website, Overview, "Regular e-bikes vs e-motos".
