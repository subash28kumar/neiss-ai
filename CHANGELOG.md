# Changelog

All notable changes to NEISS-AI are listed here.

## v1.6.1 — 2026-11-08
- Hazard Watch now gives **per-population rates**: ED visits (and admissions) per 100,000 US residents for both years, with a 95% range for the newer year (`rate_base`, `rate`, `rate_low`, `rate_high` in every `hazard_scan_<year>.csv`). Population: US Census Bureau July 1 estimates (Vintage 2025 for 2020–2025; intercensal 2010–2020 series for 2019), in `model/us_population.csv`; years without a population row get no rate.
- 2025 rates per 100,000: e-bikes 17.5 → 30.0, e-scooters 34.9 → 48.5, power workshop grinders 3.0 → 5.5.
- Website Hazard Watch table and the two-page brief show the rates. Flags are unchanged (the scan already compares each product with all NEISS visits, which grows with the population).

## v1.6.0 — 2026-11-08
- New: **Hazard Watch**, an emerging-hazard scan of every NEISS product code (`neissai.hazards`). For each year (or the same months of two years) it compares weighted national ED visits and hospital admissions with the year before and measures the **excess** rise above the change in all of NEISS, so a general weights jump (about +18% in 2024) does not flag every product. Standard errors use Taylor linearization with hospitals as clusters within strata, including hospitals with no cases; single-year totals equal `neissai.total` (bicycles 2025: 420,962, SE 38,649). Flags need a Benjamini–Hochberg false discovery rate below 5% across all products, a rise of at least the minimum detectable change (80% power) and a stable estimate by CPSC's rule.
- New commands: `neissai hazard-export` builds the scan's input tables (`clusters.csv`, `psu.csv`, `terms.csv`) from the downloaded CPSC files; `neissai hazards` runs the scan. Admissions are dispositions 2, 4, 5 or 8, read correctly when the disposition is stored as text.
- CPSC code changes: e-bikes/mopeds (3215 → 5045/5046, 2024), scooters and hoverboards (1329/5042 → 5022–5025, 2020) and cribs (1543/1545 → 1552, 2021) are combined only for comparisons that cross the change. Automatic code-change detection finds exactly these three changes in 2019–2025; new codes are never flagged.
- New: emerging-words check on the injury stories (Poisson test plus a stricter test that allows for normal year-to-year drift in wording), a filter for writing-style words (PT, YOM, DX, STATED, typos), and a short reading list of product and device words per year (`hazard_words_<year>.csv`; spellings such as "electric bicycle" and "ebike" are merged under E-BIKE).
- New: product names for all CPSC product codes (`model/product_codes.csv`, from CPSC's NEISS format file, with e-mobility and flagged codes written out in full).
- `neissai.hazards.watch()` tests products chosen in advance on their own (no all-product correction).
- Results 2020–2025: 2025 flags e-bikes (5045: 59,600 → 102,600), e-scooters (5022: 118,500 → 165,700) and power workshop grinders, buffers or polishers (897: 10,200 → 18,800) for ED visits; infant and toddler play centers (1550; small numbers, check); floors (1807; ED visits and admissions; sudden April 2025 jump at most hospitals, most likely coding practice). 2024 has no flags. 2020–2021 are labelled "pandemic years, interpret with caution" (33 and 27 ED-visit flags). Retrospective: e-bike wording ("electric bike", then "e-bike") rose faster than all stories every year from 2021, three years before CPSC's separate e-bike code; e-scooter visits were flagged in 2021 (+74%). The old moped/power-assisted cycle code 3215 is not flagged in the all-product scan (yearly estimates fail CPSC's stability rule); tested on its own it rises in 2021–2023.
- Website: new **Hazard Watch** tab with the 2025 signals, the e-bike early-warning check, CSV downloads for every year and the two-page brief `NEISS-AI_Hazard_Watch_2025.pdf`.
- Automatic updates: when the monthly refresh finds a new year of NEISS data, it also rescans every product code (`neissai.hazards.update_site_hazards`) and writes `docs/data/hazards/summary.json`; the Hazard Watch tab then shows the newest year's signals by itself. If the scan fails, the rest of the refresh still publishes.
- Tests: 19 new in `tests/test_hazards.py`; two run only when `NEISSAI_HAZARD_EXPORT` points to the full export.

## v1.5.0 — 2026-10-29
- Colab notebook: new steps "Injuries by month" and "Regular e-bikes vs e-motos".
- Website: "Embed this chart" — a short HTML snippet lets other websites show a live NEISS-AI chart (e-bike trend, e-bikes and e-scooters, or regular e-bikes vs e-motos) with the source and citation under it (`docs/embed.html?chart=ebike|devices|emoto`, optional `&theme=light|dark`). Embed buttons on the Overview charts and on the For journalists page. Closes #3.
- New: e-bike vs e-moto. `neissai.ebike_type()` and `neissai.add_ebike_type()` sort each e-bike story into regular e-bike, likely e-moto (e-moto wording such as electric dirt bike or engine-powered, or the rider's own speed above 28 mph) or unclear. Built on 320 stories, then locked and tested once on 240 new stories labelled blind: 98.4% in the right group across all e-bike stories (95% CI 97.2–99.5%); likely e-moto share 2.0% by the rule vs 2.0% by the reviewers. See `validation/EBIKE_TYPE.md`. Likely e-motos are 1.8–2.7% of e-bike emergency visits in every year 2019–2025 (2025: about 1,900 of 101,600), a lower bound because stories name an e-moto only when the writer says so.
- Website: new "Regular e-bikes vs e-motos" chart on the Overview (visits with 95% bands, or share of e-bike visits), with table and CSV download. `scripts/update_site.py` now also writes `by_ebike_type`.

## Earlier unreleased — 2026-10-26
- Website: new "Injuries by month" chart on the Overview (any year 2019–2025; visits with 95% bands, or each month's share of the year to compare seasons with regular bicycles), with table and CSV download. Suggested by a transport safety researcher. `scripts/update_site.py` now also writes monthly estimates (`by_month` in `docs/data.json`).
- Website: new "For journalists" page (`docs/press.html`) with key numbers, a free-to-use chart and sourcing notes; linked from the header.
- Website: "Cite this tool" now offers BibTeX and RIS downloads for reference managers.
- Data fix: the website is now built from every micromobility record in CPSC's complete annual NEISS files. The earlier site used smaller extracts that missed some records whose product codes appeared in the second or third product field or whose story was the only clue (found by checking the new Colab notebook against the site). E-bike and e-scooter estimates change by less than 1% from 2021 on (2025 e-bike: 101,600, 95% CI 69,700–133,600, up 71% from 2024); bicycle estimates rise about 2–3% and skateboard and hoverboard estimates up to about 14%. Accuracy check updated: 2022–2024 e-bike estimates are within 5% of CPSC's published figures. The Colab notebook and the website now give identical numbers.
- New Google Colab quickstart notebook (`notebooks/NEISS-AI_Quickstart.ipynb`): installs NEISS-AI, gets the public NEISS files, and reproduces the national estimates by year and device, a trend chart and hospital-stay shares, with a citation cell. "Open in Colab" link in the README.
- Continuous testing: the test suite now runs automatically on Python 3.10–3.12 for every change (`.github/workflows/tests.yml`); README badges for tests, PyPI, DOI and Colab.
- Website: new 'Fact sheets' section with Fact Sheet 1, 'E-bike injuries in the United States, 2019–2025' (one-page PDF with citation).
- Website: every table now has "Download table (CSV)" (estimate, 95% CI, records, unstable flag) and "Copy citation"; each CSV starts with the title, citation, method note, data date and a link to the view.
- Website: answers in "Ask a question" show a citation line.
- Package published on PyPI: `pip install neissai` (https://pypi.org/project/neissai/), released automatically from GitHub with PyPI Trusted Publishing. Licence metadata updated to the SPDX format.
- Website: overview note explains that the 2024–2025 rise is not a coding effect (both years use CPSC's separate e-bike code).

## v1.4.0 — 2026-10-21
- InjuryCoder: new `circumstances` module reads motor vehicle involvement and helmet status (worn / not worn / not mentioned) from injury stories. Tested on 300 held-out stories: motor vehicle 98.3% correct (sensitivity 93.6%, precision 95.7%); helmet 300/300 (see `validation/`).
- Fixes: the old motor vehicle flag found only about half of real cases; the old "helmet worn" flag counted unclear wording such as "HELMET NS" as worn. Website data rebuilt with the new flags (national injury counts unchanged).
- New `helmet_status` column; tests for the new rules.
- Website: third accuracy check added to "How we know it's accurate".
- Device-labels dataset version 1.1 on Zenodo with the corrected helmet and motor vehicle columns (DOI 10.5281/zenodo.23550382); website and README citations updated.
- Archived on Zenodo (DOI 10.5281/zenodo.23550272); citations on the website, README and CITATION.cff updated to v1.4.0. Chart credit lines use the all-versions DOI 10.5281/zenodo.23306744.

## 2026-10-21
- Website: new "How we know it's accurate" section (classifier AUC 0.995 explained; national e-bike estimates for 2022–2024 compared with CPSC's published figures, all within 4%).
- Website: neutral link-preview image.
- Added CONTRIBUTING.md and this changelog.

## 2026-10-18
- Website: citation for the NEISS-AI device-labels dataset (Zenodo DOI 10.5281/zenodo.23461211); fixed header links to "Cite" and "Feedback".

## v1.3 — 2026-10-15
- Website: "Download chart" button on every chart, with a citation credit line.
- Website: social preview image and link-preview tags.

## v1.2 — 2026-10-14
- Website: "Cite this tool" (software and preprint DOIs) and "Share how you use it" feedback link.
- README and CITATION.cff updated with Zenodo DOIs.

## v1.1.0 — 2026-10-11
- Web app: plain-English question box, data explorer with CSV download and share links, injury-story search.
- Automatic monthly refresh with GitHub Actions.
- Archived on Zenodo (DOI 10.5281/zenodo.23306745).

## v1.0.0 — 2026-10-11
- First release: Python package and command-line tool for national e-bike and e-scooter injury estimates from NEISS, with a text classifier for code 3215 records and survey-correct 95% confidence intervals.
