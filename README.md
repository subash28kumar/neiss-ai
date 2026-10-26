# NEISS-AI

[![Tests](https://github.com/subash28kumar/neiss-ai/actions/workflows/tests.yml/badge.svg)](https://github.com/subash28kumar/neiss-ai/actions/workflows/tests.yml) [![PyPI](https://img.shields.io/pypi/v/neissai)](https://pypi.org/project/neissai/) [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23550272.svg)](https://doi.org/10.5281/zenodo.23550272) [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/subash28kumar/neiss-ai/blob/main/notebooks/NEISS-AI_Quickstart.ipynb)

**AI-assisted national injury estimates from US emergency department narratives.**

NEISS-AI turns the US Consumer Product Safety Commission's [NEISS](https://www.cpsc.gov/Research--Statistics/NEISS-Injury-Data) data into consistent national estimates for e-bikes, e-scooters, bicycles and other micromobility devices, with survey-correct 95% confidence intervals.

**Live web app:** https://subash28kumar.github.io/neiss-ai/

The web app has four parts, all free and running in the browser:

- **Overview:** headline numbers and trends for e-bikes, e-scooters and kick scooters.
- **Ask a question:** type a question in plain English (for example, *"How many teenagers broke a bone on an e-scooter in 2025?"*) and get a national estimate with a 95% confidence interval, a trend chart and an "Understood as" line showing how the question was read.
- **Explore the data:** filter by device, years, age, sex, injury, body part, outcome and circumstance; download the results as CSV; share a link to any view.
- **Search injury stories:** search the hospital narratives (for example *battery*, *hit by car*) to see national estimates by year and real example stories.

The site refreshes itself: a GitHub Actions workflow (`.github/workflows/refresh.yml`) checks monthly for a new year of NEISS data, reruns the tool and republishes the site. It never publishes fewer years than the site already shows.

## Why it exists

In January 2024, CPSC gave e-bikes their own product code (5045). Before then, e-bikes shared code 3215 ("mopeds or power-assisted cycles") with gas mopeds. Counts based on codes alone therefore jump at 2024 and cannot show a true trend.

NEISS-AI reads the short injury story in each record:

1. **Rules.** Product codes and whole-word keywords label each injury (e-bike, e-scooter, bicycle, kick scooter, hoverboard, skateboard or moped). Whole-word matching matters: "the bike" is not an "e bike".
2. **Text classifier.** For code-3215 records whose story is unclear, a classifier trained on 2024-2025 records (where 5045 and 5046 are separate) decides e-bike vs moped. It is TF-IDF + logistic regression, stored as plain JSON and run with numpy only. Five-fold cross-validated AUC: **0.995**.
3. **National estimates.** NEISS is a stratified sample of hospitals. Estimates use the survey weights and Taylor-linearized standard errors (hospitals as clusters within strata), and are flagged "unstable" by CPSC's rule (fewer than 20 records, an estimate below 1,200, or a coefficient of variation above 33%).

**Validation:** e-bike estimates for 2022-2024 are within 5% of CPSC's published figures (28,000 vs 26,800; 37,900 vs 37,600; 59,300 vs 59,200).

## Install

```
pip install neissai
```

NEISS-AI is on PyPI: https://pypi.org/project/neissai/. Requires Python 3.9+, pandas and numpy. (scikit-learn is needed only to retrain the classifier: `pip install "neissai[train]"`. For the latest development version: `pip install git+https://github.com/subash28kumar/neiss-ai`.)

## Try it in Google Colab (no install)

Open the [quickstart notebook](https://colab.research.google.com/github/subash28kumar/neiss-ai/blob/main/notebooks/NEISS-AI_Quickstart.ipynb) and click **Runtime → Run all**. In a few minutes it downloads the public NEISS files, labels each injury, and reproduces the national estimates by year and device (with 95% confidence intervals), a trend chart and hospital-stay shares. The notebook is also in this repository at `notebooks/NEISS-AI_Quickstart.ipynb`.

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

## Rebuild the website data

```
python scripts/update_site.py --data-dir data --years 2019-2025
```

## Retrain the classifier

```
python scripts/train_classifier.py --data-dir data --years 2024-2025
```

## Limits

NEISS counts emergency department visits, not riders or miles, so results are counts, not risk rates. Injuries treated elsewhere and deaths at the scene are not included. Helmet use is only what the story mentions. Early e-bike estimates (2019-2021) rest on small samples. The powered-scooter code may include some seated, moped-style scooters.

## Cite

If you use NEISS-AI, please cite the software (see `CITATION.cff` or "Cite this repository" on GitHub):

> Kumar S. NEISS-AI: AI-assisted national injury estimates from NEISS emergency department narratives. Version 1.4.0 [software]. Zenodo; 2026. https://doi.org/10.5281/zenodo.23550272
>
> To cite all versions, use https://doi.org/10.5281/zenodo.23306744 (always resolves to the latest version).

and the method paper:

> Kumar S. E-bike injuries among US children surged in 2025: national estimates from emergency department reports, 2019-2025, using machine learning to read injury narratives [preprint]. Zenodo; 2026. https://doi.org/10.5281/zenodo.23354066

and the labeled dataset:

> Kumar S. NEISS-AI device labels for US micromobility injuries, 2019–2025 [dataset]. Version 1.1. Zenodo; 2026. https://doi.org/10.5281/zenodo.23550382

Data come from the US Consumer Product Safety Commission. CPSC does not endorse this tool.

## Licence

MIT. Built by Subash Kumar (ORCID [0009-0003-6661-3424](https://orcid.org/0009-0003-6661-3424)).
