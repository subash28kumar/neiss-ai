# Run NEISS-AI on your own injury notes

This guide is for health departments, hospitals and research teams that hold their own emergency
department records and want to sort bike and scooter injuries the way NEISS-AI does:
e-bike, e-scooter, bicycle, kick scooter, hoverboard, skateboard or moped.

**Your data never leaves your computer.** NEISS-AI is free, open-source software. You install it
on your own secure machine and run it there. Nothing is uploaded or sent anywhere.

## What you need

- A table (CSV, TSV or Excel) with **one row per visit** and a column with the **note text**:
  a triage note, chief complaint or longer injury description.
- Optional, but helpful: a column with **ICD-10-CM external-cause codes** (V00 to V29).
- Python 3.9 or newer.

## Steps

**1. Install** (one time):

```
pip install neissai
```

**2. Run it on your file.** Replace the file name and column names with yours:

```
neissai label-notes my_ed_visits.csv --text-col triage_note --code-cols ecode1,ecode2 --out labelled.csv
```

Leave out `--code-cols` if you have no codes. It prints a count for each device and saves a copy of
your table with new columns:

| Column | What it holds |
| --- | --- |
| `device` | E-bike, E-scooter, Bicycle, Kick scooter, Hoverboard, Skateboard, Moped / minibike, Scooter (type not stated), Other standing micromobility, Motorcycle or moped (a motorcycle code alone, which cannot tell the two apart), Motorcycle (not micromobility), Excluded (mobility scooter, exercise bike) or Other |
| `device_how` | what decided it: words, code, code+words, or classifier (for "motorized bike" wording) |
| `ebike_type` | for e-bikes: regular e-bike, likely e-moto (electric motorcycle) or unclear |
| `helmet` | yes, no or not mentioned |
| `motor_vehicle` | True if the note describes contact with a car or other motor vehicle |
| `rider_mph` | the rider's speed, if the note gives one |
| `role` | rider, or "struck by rider" when a code says the patient was on foot and hit by the device |

**3. Check about 100 records by hand.** Pick a random 100 of the labelled rows, read each note and
write down what you think the device is. Compare with the `device` column. This tells you how well
it works on *your* notes. Different hospitals write notes differently.

**4. Adjust if needed.** If your notes use words NEISS-AI does not know (local brand names, "push
bike", hire schemes), tell us or add them to the word lists in `src/neissai/freetext.py`. Questions
are welcome by email: nivi05subhash@gmail.com.

## What to expect (honest limits)

We tested the text-only labels on 141,634 real NEISS stories (2019-2025) with the product codes
hidden, and compared them with NEISS-AI's full labels (which also use CPSC's product codes):

| Device | Same label from text alone |
| --- | --- |
| Bicycle | 99% |
| Skateboard | 97% |
| E-bike | 95% (2025 national total within 4%) |
| Moped / minibike | 93% |
| Hoverboard | 79% |
| E-scooter | 82% (most of the rest say only "scooter") |
| Kick scooter | about 6%: the note usually says only "scooter", so it is marked "type not stated" |

What this means for you:

- **"Scooter" alone cannot be sorted from the words.** If your data has ICD-10-CM codes, they settle
  it: standing e-scooter codes (V00.84-) exist from October 2020 and scooter (nonmotorized) is V00.14-.
- **E-bike codes** (electric assisted bicycle) exist from October 2022: in V20-V28 the 5th character
  is 1 (for example V28.01), in V29 the 6th character is 1. Before that, e-bikes sit under bicycle or
  motorcycle codes and the note decides.
- **Motorcycle codes** (V20-V29) also cover mopeds and motor scooters, so a code alone gives
  "Motorcycle or moped". If the note says moped, or motorcycle, that decides it. Motorcycles are not
  micromobility; leave them out of e-bike and moped counts.
- **Short notes say less.** When we kept only the first 60 characters of each story, agreement fell
  to about 72% overall, mostly because the device word was cut off. Real triage notes usually name
  the device early, but please check your own (step 3).
- **Outside the US**, ICD-10-AM and other national versions use different codes. Use the text alone,
  or pass your own code list in Python (`code_map`, see below).

Full results: [validation/freetext/RESULTS.md](https://github.com/subash28kumar/neiss-ai/blob/main/validation/freetext/RESULTS.md).

## From Python

```python
import pandas as pd
import neissai

df = pd.read_csv("my_ed_visits.csv")
labelled = neissai.label_notes(df, "triage_note", code_cols=["ecode1", "ecode2"])
print(labelled["device"].value_counts())

# Other code systems: give your own list of (code start, device, role)
my_codes = [("V10", "Bicycle", "rider"), ("V20", "Moped / minibike", "rider")]
labelled = neissai.label_notes(df, "triage_note", code_cols="ecode1", code_map=my_codes)
```

## How to cite

Kumar S. NEISS-AI: AI-assisted national injury estimates from NEISS emergency department narratives
[software]. Zenodo; 2026. https://doi.org/10.5281/zenodo.23306744
