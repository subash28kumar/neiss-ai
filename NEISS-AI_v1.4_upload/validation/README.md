# InjuryCoder validation (v1.4)

NEISS-AI v1.4 reads two circumstances that NEISS does not code: whether a motor vehicle was involved, and whether the story says a helmet was worn (`src/neissai/circumstances.py`).

## How the rules were checked

1. The rules were written using NEISS micromobility narratives outside the samples below.
2. They were refined on two random samples of 200 narratives each.
3. They were then frozen and tested once on a third random sample of **300 narratives (2019–2025) never used to build them** (`injurycoder_test_300.csv`).

Reference answers: an independent AI reviewer that never saw the rules read every narrative and labelled it from the written definitions below. Where the reviewer and the rules disagreed (5 of 300 narratives), the case was decided against the same definitions. The reference answers were not made by a human annotator.

## Definitions

- **Motor vehicle = Yes** when the patient was hit by, crashed into, or struck part of a motor vehicle (moving or parked, including a car door), or the story calls the event an MVC/MVA. Swerving to avoid a car without contact, crashes with another bike or scooter, and loading a bike into a car are **No**.
- **Helmet** is **Yes** (story says a helmet was worn), **No** (story says no helmet) or **Not mentioned** (not said, or unclear, for example "HELMET NS"). "Not mentioned" is never counted as "no helmet".

## Results on the 300-narrative test set

| | Result |
|---|---|
| Motor vehicle, correct | 295/300 = 98.3% (95% CI 96.2–99.3%) |
| Motor vehicle, real cases found (sensitivity) | 44/47 = 93.6% (82.8–97.8%) |
| Motor vehicle, flags correct (precision) | 44/46 = 95.7% (85.5–98.8%) |
| Helmet (3 answers), correct | 300/300 = 100% (98.7–100%) |

Errors: missed a bicycle hitting a tractor, a pedestrian hit by a moped and a bicycle struck by a cargo truck; false flags for "a car ran her off the road" (no contact) and "flipped over vehicle" (the rider's own motocross bike).

Run `python validation/score_injurycoder.py` to reproduce these numbers. Data: public CPSC NEISS narratives.
