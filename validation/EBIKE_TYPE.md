# E-bike or e-moto? How the rule was built and tested

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
