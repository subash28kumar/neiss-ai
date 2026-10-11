# NEISS-AI

**AI-assisted national injury estimates from US emergency department narratives.**

NEISS-AI turns the US Consumer Product Safety Commission's [NEISS](https://www.cpsc.gov/Research--Statistics/NEISS-Injury-Data) data into consistent national estimates for e-bikes, e-scooters, bicycles and other micromobility devices, with survey-correct 95% confidence intervals.

**Live dashboard:** https://subash28kumar.github.io/neiss-ai/

## Why it exists

In January 2024, CPSC gave e-bikes their own product code (5045). Before then, e-bikes shared code 3215 ("mopeds or power-assisted cycles") with gas mopeds. Counts based on codes alone therefore jump at 2024 and cannot show a true trend.

NEISS-AI reads the short injury story in each record:

1. **Rules.** Product codes and whole-word keywords label each injury (e-bike, e-scooter, bicycle, kick scooter, hoverboard, skateboard or moped). Whole-word matching matters: "the bike" is not an "e bike".
2. **Text classifier.** For code-3215 records whose story is unclear, a classifier trained on 2024-2025 records (where 5045 and 5046 are separate) decides e-bike vs moped. It is TF-IDF + logistic regression, stored as plain JSON and run with numpy only. Five-fold cross-validated AUC: **0.995**.
3. **National estimates.** NEISS is a stratified sample of hospitals. Estimates use the survey weights and Taylor-linearized standard errors (hospitals as clusters within strata), and are flagged "unstable" by CPSC's rule (fewer than 20 records, an estimate below 1,200, or a coefficient of variation above 33%).

**Validation:** e-bike estimates for 2022-2024 are within 4% of CPSC's published figures (27,800 vs 26,800; 37,600 vs 37,600; 59,000 vs 59,200).

## Install

```
pip install git+https://github.com/subash28kumar/neiss-ai
```

Requires Python 3.9+, pandas and numpy. (scikit-learn is needed only to retrain the classifier: `pip install "neissai[train] @ git+https://github.com/subash28kumar/neiss-ai"`.)

## Use from the command line

Download the annual NEISS files (for example `neiss2019.tsv` ... `neiss2025.tsv`) from the [CPSC NEISS page](https://www.cpsc.gov/Research--Statistics/NEISS-Injury-Data) into a folder called `data`, or try `neissai download --years 2019-2025 --data-dir data`. Then:

```
neissai micromobility --years 2019-2025 --data-dir data --out-dir results
```

This prints a table of national estimates and saves:

| File | Contents |
|---|---|
| `estimates_by_year_device.csv` | national ED visits by year and device, 95% CI, CV, records, unstable flag |
| `estimates_by_year_device_age.csv` | the same by age group (0-17, 18-64, 65+) |
| `shares_by_device.csv` | weighted shares hospitalized, head/face injury, motor vehicle involved, no helmet stated, alcohol |
| `micromobility_records.csv` | every labelled record, with device, label source and classifier probability |

Check a single story:

```
neissai classify "14YOM FELL OFF HIS ELECTRIC BIKE GOING 20MPH"
```

## Use from Python

```python
import neissai

df = neissai.read_neiss("data", years="2019-2025")
df = neissai.add_outcomes(neissai.label_devices(df))
mm = df["device"].isin(neissai.DEVICES)

# Pass the full table plus a filter, so the variance uses the whole sample design
by_year = neissai.national_estimates(df, by=["year", "device"], where=mm)
kids = neissai.national_estimates(df, by=["year"], where=(df["device"] == "E-bike") & (df["age_group"] == "0-17"))
hosp = neissai.shares(df, "hospitalized", by=["device", "age_group"], where=mm)
```

## Retrain the classifier

```
python scripts/train_classifier.py --data-dir data --years 2024-2025
```

## Limits

NEISS counts emergency department visits, not riders or miles, so results are counts, not risk rates. Injuries treated elsewhere and deaths at the scene are not included. Helmet use is only what the story mentions. Early e-bike estimates (2019-2021) rest on small samples. The powered-scooter code may include some seated, moped-style scooters.

## Cite

If you use NEISS-AI, please cite the software (see `CITATION.cff` or "Cite this repository" on GitHub):

> Kumar S. NEISS-AI: AI-assisted national injury estimates from NEISS emergency department narratives. Version 1.0.0. 2026. https://github.com/subash28kumar/neiss-ai

and the method paper:

> Kumar S. E-bike injuries among US children surged in 2025: national estimates from emergency department reports, 2019-2025, using machine learning to read injury narratives. medRxiv preprint, 2026.

Data come from the US Consumer Product Safety Commission. CPSC does not endorse this tool.

## Licence

MIT. Built by Subash Kumar (ORCID [0009-0003-6661-3424](https://orcid.org/0009-0003-6661-3424)).
