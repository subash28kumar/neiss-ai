# Text-only labels compared with NEISS-AI's full labels

**Question:** if a dataset has no CPSC product codes (a state's emergency department records, or
another country's), how close do NEISS-AI's labels get from the note text alone?

**Data:** every NEISS 2019-2025 record that NEISS-AI labels as one of its 7 micromobility devices
(141,634 records, the site's `docs/data/records.json` and `stories.json`). NEISS-AI's full labels use
the product codes AND the story. Here the codes were hidden and `neissai.freetext.label_notes` read
only the story. Two versions: the full NEISS story, and a SHORT version (first 60 characters) as a
rough stand-in for a brief triage note.

**Important:** this measures agreement with NEISS-AI's full labels, not with a human gold standard,
and only among records that are micromobility injuries. It cannot show false alarms among
non-micromobility records; check a hand sample of your own data for that (see docs/own-notes.md).

Script: `validation/freetext/evaluate.py`. Raw output: `results.json`.

## Full NEISS stories (codes hidden)

| Full label | Records | Same label from text (raw / weighted) | What text-only said instead (top) |
| --- | ---: | --- | --- |
| E-bike | 5,793 | 94.9% / 95.0% | Bicycle 225, Other 25, Moped / minibike 23 |
| E-scooter | 13,363 | 82.7% / 82.3% | Scooter (type not stated) 2,068, Other 65, Bicycle 53 |
| Bicycle | 77,786 | 99.1% / 99.0% | Other 634, Motorcycle (not micromobility) 26, Moped / minibike 21 |
| Kick scooter | 17,566 | 7.8% / 5.9% | Scooter (type not stated) 16,032, Bicycle 88, Other 63 |
| Hoverboard | 4,499 | 82.5% / 78.6% | Other standing micromobility 303, Other 256, Skateboard 178 |
| Skateboard | 16,310 | 96.9% / 97.0% | Other 435, Bicycle 39, Scooter (type not stated) 21 |
| Moped / minibike | 6,317 | 93.0% / 93.9% | Bicycle 112, Scooter (type not stated) 109, E-bike 74 |
| **All 7** | **141,634** | **85.0% / 86.6%** | |

National 2025 estimates: e-bike 97,900 from text alone vs 101,600 with codes (-3.6%); e-scooter 139,200 vs 164,400 (-15%, mostly notes that say only "scooter").

Re-run on November 22, 2026, after the independent-review fixes (unpowered scooters are kick scooters; moped-code "scooter" stories are not e-bikes). The first run (v1.7.0) gave 84.7% / 86.3% overall.

## Short notes (first 60 characters)

All 7: 71.5% raw / 72.0% weighted. E-bike 71.6%, E-scooter 61.7%, Bicycle 85.1%, Skateboard 82.4%,
Hoverboard 73.5%, Moped 75.7%, Kick scooter 6.5%. The drop is mostly "Other": NEISS stories start
with age and sex and often name the device after the 60th character. Real triage notes usually name
the device earlier, so this is a pessimistic stand-in; check your own notes.

## What it means

- Text alone is strong for bicycles, skateboards, e-bikes and mopeds when the note names the device.
- "Scooter" alone cannot be sorted into kick or electric from the words; ICD-10-CM codes (V00.84-
  standing e-scooter from Oct 2020; V00.14- nonmotorized scooter) settle it, which is why the code
  column is supported.
- The ICD-10-CM mapping follows the NEMSIS micromobility case definition (June 27, 2023); it is
  checked by unit tests (tests/test_freetext.py) but has not yet been tested on a real coded dataset.
  ICD-10-CM motorcycle codes (V20-V29) include mopeds and motor scooters, so a motorcycle code alone
  gives "Motorcycle or moped"; the words then decide (moped, or "Motorcycle (not micromobility)").
  V29.81x (motorcycle and military vehicle) is not an e-bike code.
