# Changelog

All notable changes to NEISS-AI are listed here.

## Unreleased — 2026-10-24
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
