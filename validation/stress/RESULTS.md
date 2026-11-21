# Messy-notes stress test (November 2026)

How well NEISS-AI's text rules hold up when injury notes are written differently from NEISS. Nothing here changes NEISS-AI or its published numbers; it only measures. Deterministic (seed 2026). Run: `python validation/stress/run_stress.py`.

Messy versions: lower case; clinic format ('29 yo male', 'Impression:' instead of 'DX'); other spellings ('EBIKE', 'E BIKE', 'ELEC BIKE', 'W/O', 'AUTO'); typos in 5% or 10% of words (swapped, dropped or doubled letters, keywords included); and all combined. Ranges are 95% Wilson intervals.

## 1. E-bike vs e-moto rule (locked fresh test, 240 stories)

| Version | right | e-moto found |
|---|---|---|
| clean | 97.1% (94.1-98.6), 233/240 | 100.0% (83.9-100.0), 20/20 |
| lower case | 97.1% (94.1-98.6), 233/240 | 100.0% (83.9-100.0), 20/20 |
| clinic format | 97.1% (94.1-98.6), 233/240 | 100.0% (83.9-100.0), 20/20 |
| other spellings | 95.8% (92.5-97.7), 230/240 | 85.0% (64.0-94.8), 17/20 |
| typos (5% of words) | 93.3% (89.4-95.9), 224/240 | 100.0% (83.9-100.0), 20/20 |
| typos (10% of words) | 93.3% (89.4-95.9), 224/240 | 95.0% (76.4-99.1), 19/20 |
| all combined | 93.8% (89.9-96.2), 225/240 | 100.0% (83.9-100.0), 20/20 |

## 2. Motor vehicle and helmet (locked test, 300 stories)

| Version | motor vehicle right | crashes found | helmet right |
|---|---|---|---|
| clean | 98.3% (96.2-99.3), 295/300 | 93.6% (82.8-97.8), 44/47 | 100.0% (98.7-100.0), 300/300 |
| lower case | 98.3% (96.2-99.3), 295/300 | 93.6% (82.8-97.8), 44/47 | 100.0% (98.7-100.0), 300/300 |
| clinic format | 98.3% (96.2-99.3), 295/300 | 93.6% (82.8-97.8), 44/47 | 100.0% (98.7-100.0), 300/300 |
| other spellings | 98.3% (96.2-99.3), 295/300 | 93.6% (82.8-97.8), 44/47 | 100.0% (98.7-100.0), 300/300 |
| typos (5% of words) | 98.3% (96.2-99.3), 295/300 | 93.6% (82.8-97.8), 44/47 | 99.0% (97.1-99.7), 297/300 |
| typos (10% of words) | 98.3% (96.2-99.3), 295/300 | 93.6% (82.8-97.8), 44/47 | 98.0% (95.7-99.1), 294/300 |
| all combined | 98.3% (96.2-99.3), 295/300 | 93.6% (82.8-97.8), 44/47 | 99.3% (97.6-99.8), 298/300 |

## 3. Device from the note alone (no CPSC product codes, as in a state's own ER data)

2024-2025 NEISS records; reference = CPSC's own device code. 200 each of e-bike, e-scooter, bicycle, and 200 other micromobility records.

| Version | E-bike found | E-scooter found | Bicycle found | E-bike calls right |
|---|---|---|---|---|
| clean | 94.5% (90.4-96.9), 189/200 | 91.0% (86.2-94.2), 182/200 | 97.5% (94.3-98.9), 195/200 | 100.0% (98.0-100.0), 189/189 |
| lower case | 94.5% (90.4-96.9), 189/200 | 91.0% (86.2-94.2), 182/200 | 97.5% (94.3-98.9), 195/200 | 100.0% (98.0-100.0), 189/189 |
| clinic format | 94.5% (90.4-96.9), 189/200 | 91.0% (86.2-94.2), 182/200 | 97.5% (94.3-98.9), 195/200 | 100.0% (98.0-100.0), 189/189 |
| other spellings | 80.0% (73.9-85.0), 160/200 | 91.0% (86.2-94.2), 182/200 | 97.5% (94.3-98.9), 195/200 | 100.0% (97.7-100.0), 160/160 |
| typos (5% of words) | 86.5% (81.1-90.6), 173/200 | 84.0% (78.3-88.4), 168/200 | 93.5% (89.2-96.2), 187/200 | 100.0% (97.8-100.0), 173/173 |
| typos (10% of words) | 81.0% (75.0-85.8), 162/200 | 78.5% (72.3-83.6), 157/200 | 91.5% (86.8-94.6), 183/200 | 100.0% (97.7-100.0), 162/162 |
| all combined | 81.0% (75.0-85.8), 162/200 | 80.5% (74.5-85.4), 161/200 | 95.0% (91.0-97.3), 190/200 | 100.0% (97.7-100.0), 162/162 |

E-bike records missed from the note alone (clean), what the note was read as: Bicycle 9, Other 2

Sample misses:

- 22YOM PRESENTS WITH MVCA YESTERDAY, STATES HE WAS RIDING ELECTRONIC BIKE WITH HELMET ON WHEN A CAR HIT HIM FROM THE BACK AND HE FELL FORWARD
- 6YOF REPORTS SHE WAS STRUCK BY A MOTORIZED BICYCLE WHILE CROSSING THE STREET AND SHE FELL TO THE GROUND AND HIT HER HEAD, SHE DID NOT LOSE C
- 9YOM WAS RIDING A MOTORIZED BIKE, WHEN THE BIKE WENT TO THE LEFT AND HE FELL FORWARD. REPORTS HE LANDED ON HIS RIGHT WRIST, AND SUSTAINED AB
- 34YOM C/O FALL FROM A BATTERY BIKE ACCIDENT. INJURIES TO LEFT SHOULDER, HANDS, AND KNEES. ABRASIONS TO LEFT SHOULDER, BOTH KNEES, AND BOTH P
- 59 YOM RIDING MOTORIZED BICYCLE HAD ACCIDENT NO HELMET DX ACUTE STRAIN NECK MUSCLE
- 13 YOM WAS HELMETED RIDING A MOTORIZED BIKE WHEN HE CRASHED. HE REPORTS PAIN AROUND HIS EYE. DX: MOTOR VEHICLE ACCIDENT
- 67YOM DRINKING ALCOHOL AND FELL OFF ELECTRIC BOKE WHEN TIPPED OVER. BAC 91. KNEE PAIN DX AMS
- 31YOM WAS RIDING A MOTORIZED BICYCLE AND FELL OFF WHILE INTOXICATED NO BAC OBTAINED DX: STRAINED LEFT ANKLE

Example of one note in every version:

- **clean:** 29YOM WAS RIDING AN ELECTRIC BICYCLE AND WAS HIT BY A CAR DX CLOSED HEAD INJURY, ABRASION LEFT FOOT
- **lower case:** 29yom was riding an electric bicycle and was hit by a car dx closed head injury, abrasion left foot
- **clinic format:** 29 yo male WAS RIDING AN ELECTRIC BICYCLE AND WAS HIT BY A CAR DIAGNOSIS: CLOSED HEAD INJURY, ABRASION LEFT FOOT
- **other spellings:** 29YOM WAS RIDING AN ELEC BICYCLE AND WAS HIT BY A CAR DX CLOSED HEAD INJURY, ABRASION LEFT FOOT
- **typos (5% of words):** 29YOM WAS RIDING AN ELECTRIC BICYCLE AND WAS HIT BY A CAR DX CLOSED HEAD INJURY, ABRASION LEEFT FOOT
- **typos (10% of words):** 29YOM WAS RIDING AN ELECTRIC BICYCLE AND WAS HIT BY A CAR DX CLOSED HEAD IJNURY, ABRASION LFT FOOT
- **all combined:** 29 year old man was riding an electric bicycle and was hit by a car dx closed head injury, abrasion left foot

## 4. Same tests with a PROTOTYPE clean-up step (validation/stress/cleanup_proto.py)

The clean-up turns common spellings (ELEC BIKE, ELECTRONIC BIKE, BATTERY BIKE, MI/HR, IMPRESSION:) and one-letter typos in about 17 key words into the words the rules already know. It was built while looking at these same tests, so these numbers are optimistic; it must be re-tested on fresh notes before any use. It is NOT used by NEISS-AI's published numbers.

| Version | e-bike vs e-moto right | motor vehicle right | helmet right | E-bike found (text only) | E-scooter found | Bicycle found | E-bike calls right |
|---|---|---|---|---|---|---|---|
| clean | 97.1% (233/240) | 98.3% (295/300) | 100.0% (300/300) | 95.5% (191/200) | 92.5% (185/200) | 98.0% (196/200) | 100.0% (191/191) |
| lower case | 97.1% (233/240) | 98.3% (295/300) | 100.0% (300/300) | 95.5% (191/200) | 92.5% (185/200) | 98.0% (196/200) | 100.0% (191/191) |
| clinic format | 97.1% (233/240) | 98.3% (295/300) | 100.0% (300/300) | 95.5% (191/200) | 92.5% (185/200) | 98.0% (196/200) | 100.0% (191/191) |
| other spellings | 97.1% (233/240) | 98.3% (295/300) | 100.0% (300/300) | 90.5% (181/200) | 92.5% (185/200) | 98.0% (196/200) | 100.0% (181/181) |
| typos (5% of words) | 96.7% (232/240) | 98.3% (295/300) | 100.0% (300/300) | 93.5% (187/200) | 92.5% (185/200) | 96.5% (193/200) | 100.0% (187/187) |
| typos (10% of words) | 95.0% (228/240) | 98.3% (295/300) | 100.0% (300/300) | 92.0% (184/200) | 91.5% (183/200) | 95.0% (190/200) | 100.0% (184/184) |
| all combined | 95.4% (229/240) | 98.3% (295/300) | 100.0% (300/300) | 87.5% (175/200) | 91.0% (182/200) | 96.0% (192/200) | 100.0% (175/175) |

## What this means (plain English)

- Motor vehicle and helmet answers barely change with messy notes (98-100% right in every version).
- The e-bike vs e-moto rule stays above 93% right even with typos and other spellings; speed written as 'MI/HR' was its main weak spot.
- The biggest risk for a state's own data is finding e-bikes and e-scooters from the note alone, with no CPSC product code: 94-95% found on clean notes, about 80% with heavy typos or other spellings. When the rules do say 'e-bike', they were right every time (no false alarms).
- Weak spots found: 'ELEC BIKE', 'ELECTRONIC BIKE', 'BATTERY BIKE', typos inside key words ('ELECTRIC BOKE'), speed units like 'MI/HR', and 'motorized bike' (which cannot be decided from the words alone).
- A clean-up step fixes much of this (prototype above), but it must be tested on fresh notes, and on a sample of the agency's own notes labelled by their staff, before any agency relies on it.
- Limits: the messy versions are simulated. Real notes from another hospital system can differ in ways not tested here (templates, different abbreviations, longer notes). That is why any agency pilot starts with a ~200-note accuracy check by their own staff.
