# Text-only labels compared with NEISS-AI's full labels

**Question:** if a dataset has no CPSC product codes (a state's emergency department records, or
another country's), how close do NEISS-AI's labels get from the note text alone?

**Data:** every NEISS 2019-2025 record that NEISS-AI labels as one of its 7 micromobility devices
(141,635 records, the site's `docs/data/records.json` and `stories.json`). NEISS-AI's full labels use
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
| E-bike | 5,831 | 94.3% / 94.6% | Bicycle 225, Scooter (type not stated) 31, Other 25 |
| E-scooter | 14,579 | 80.5% / 79.9% | Scooter (type not stated) 2,140, Kick scooter 459 |
| Bicycle | 77,786 | 99.1% / 99.0% | Other 634 |
| Kick scooter | 16,340 | 1.3% / 1.5% | Scooter (type not stated) 15,962 |
| Hoverboard | 4,499 | 82.5% / 78.6% | Other standing micromobility 303, Other 256, Skateboard 178 |
| Skateboard | 16,309 | 96.9% / 97.0% | Other 435 |
| Moped / minibike | 6,291 | 94.2% / 94.8% | Bicycle 114, Scooter (type not stated) 83, E-bike 74 |
| **All 7** | **141,635** | **84.7% / 86.3%** | |

National 2025 estimates: e-bike 97,900 from text alone vs 101,600 with codes (-3.6%); e-scooter
140,400 vs 168,800 (-17%, mostly notes that say only "scooter").

## Short notes (first 60 characters)

All 7: 71.3% raw / 71.8% weighted. E-bike 71.6%, E-scooter 59.7%, Bicycle 84.0%, Skateboard 82.3%,
Hoverboard 68.0%, Moped 77.0%, Kick scooter 1.0%. The drop is mostly "Other": NEISS stories start
with age and sex and often name the device after the 60th character. Real triage notes usually name
the device earlier, so this is a pessimistic stand-in; check your own notes.

## What it means

- Text alone is strong for bicycles, skateboards, e-bikes and mopeds when the note names the device.
- "Scooter" alone cannot be sorted into kick or electric from the words; ICD-10-CM codes (V00.84-
  standing e-scooter from Oct 2020; V00.14- nonmotorized scooter) settle it, which is why the code
  column is supported.
- The ICD-10-CM mapping follows the NEMSIS micromobility case definition (June 27, 2023); it is
  checked by unit tests (tests/test_freetext.py) but has not yet been tested on a real coded dataset.
