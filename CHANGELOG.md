# Changelog

All notable changes to NEISS-AI are listed here.

## E-moto range and "electric bike" note — 2026-11-21

- Improved after outside expert review. The e-bike vs e-moto card now always shows the e-moto
  share as a range for the latest year: at least the "likely e-moto" share, up to that share plus
  the "unclear" stories (2025: 1.5% to 7.2%), with a note that the true share is probably higher.
- New note: "electric bike" in a hospital note does not prove the vehicle was a legal e-bike, and
  a stated speed of 20 to 28 mph is not counted as an e-moto (a legal Class 3 e-bike assists to 28 mph).
- Labelling page: new Set D (which vehicle? 120 stories, 2019-2023) for a blind human check.
- Validation: messy-notes stress test (validation/stress/RESULTS.md).

## State forecasts — 2026-11-20

- "Your state" and every state brief now show a forecast for 2026–2028: the national forecast
  (tested on past years) times the state's age-adjusted share of national visits in 2025, with
  80% ranges. Assumes each state keeps its 2025 share; the 51 state forecasts add up to the
  national forecast (checked by a test). New "Forecast for every state" table with CSV download.

## Forecasts 2026–2030, tested on past years — 2026-11-20

- New **"Looking ahead"** section on the Overview: forecasts for e-bikes, e-scooters, kick scooters
  and bicycles, 1–5 years ahead, with 80% ranges. Method: "slowing growth" (damped trend on the log
  scale); the slowing factor (0.8) was chosen by back-testing forecasts made from data up to 2022,
  2023 and 2024 for six devices, using the one-standard-error rule (most cautious value that tests
  about as well as the best).
- Back-test (36 forecasts): typical miss 12% one year ahead, 18% two years ahead; the 80% range
  caught the real value 15/18, 10/12 and 5/6 times at 1, 2 and 3 years ahead. Years beyond 3 ahead
  cannot be tested yet and are shown as scenarios.
- **Locked 2026 forecast** (`docs/data/forecast_locked.json`, with a fingerprint checked by a test):
  never changed after publication; when CPSC releases 2026 data the site shows forecast vs actual.
- `neissai.forecast`, `scripts/build_forecast.py`, `tests/test_forecast.py`. The monthly refresh now
  also rebuilds the forecast, the state estimates and the state briefs.

## State briefs and age-adjusted state estimates — 2026-11-20

- **"Your state" is now age-adjusted.** For each of 7 age groups (under 5, 5–13, 14–17, 18–24,
  25–44, 45–64, 65+), the national estimate for that age group is multiplied by the state's share of
  the US population in that age group, then added up. A younger state gets a higher expected number
  than population alone suggests (Utah e-bikes +6%), an older one a lower number (Maine −4%). The
  population-only number is still shown beside it for comparison.
- 95% ranges use the same survey-correct method as every national estimate (each record's weight is
  multiplied by its age group's state factor; Taylor linearization, hospitals as clusters within
  strata). The 51 age-adjusted state estimates add up exactly to the national estimate.
- Population: US Census Bureau Vintage 2025, SC-EST2025-ALLDATA6 (July 1 resident population by
  single year of age). `scripts/import_census_age.py` checks that every state-year (51 × 2020–2025)
  adds up exactly to the official totals already used by the site (NST-EST2025-POP).
- **New one-page PDF brief for every state** (`docs/briefs/`), linked from the state view
  ("Download one-page brief"): e-bike, e-scooter and bicycle numbers with 95% ranges, the
  2020–2025 trend, e-bike visits by age, method, limits and a ready-to-use citation.
- New module `neissai.state`, scripts `build_state_estimates.py` and `build_state_briefs.py`,
  and tests (`tests/test_state_estimates.py`). The Data Pack "Expected by state" sheet now uses the
  age-adjusted numbers.

## E-bike vs moped classifier v2 — 2026-11-19

- Retrained with a deterministic 70/15/15 train/validation/test split (by case number): trained on
  70%, regularisation chosen on the 15% validation set, final model fit on 85%, scored once on the
  locked 15% test (833 stories): AUC 0.998 (95% CI 0.996–0.999), accuracy 98.0%, sensitivity
  98.6%, specificity 96.6%. Replaces the five-fold cross-validated v1 (AUC 0.995), which had no
  untouched test set.
- Website rebuilt with the new model: e-bike estimates for 2019–2023 change by 0.2–1.2% (40
  records switch between e-bike and moped); 2024–2025 unchanged.

## E-bike vs e-moto rule v2 — 2026-11-18

- Rebuilt on 920 development stories (old 240-story test retired into development, plus 360 new
  stories labelled blind), then locked and tested once on 240 fresh stories: 98.9% in the right
  group (95% CI 97.9–99.7%; raw 233/240), up from 98.6% / 229 for v1.4 on the same stories.
  Single "likely e-moto" calls right about 19 times in 20 (was 3 in 4).
- Fixes: "motorized bike" is unclear at any speed; guessed or downhill speeds are unclear;
  "bike vs e-bike" is unclear; clutch = e-moto; "fast"/speeds of other vehicles ignored.
- E-bike type estimates on the website recalculated (2025 likely e-moto 1,600, 1.5%).
- Rule fingerprint is checked by a test so it cannot change silently.

## Website update — 2026-11-18 (learning from people)

- New **Set C: help train** on the labelling page: the 200 hardest e-bike stories, chosen by a
  fixed scoring rule, plus 22 spot-check stories with known answers.
- New `neissai.learn`: trusted human answers become a "human memory" with guardrails (approved
  reviewers only, spot checks, at least two people agreeing, locked test stories never learned).
  Same story -> the reviewers' answer; near-identical story -> the closest labelled story's
  answer; otherwise the rules answer as before.
- New `validation/ingest_human_labels.py` and `validation/check_learning.py` (a new memory is
  published only if accuracy on the locked tests does not drop). See `validation/learning/README.md`.
- "Is an answer wrong? Tell me" button on the story explainer.
- No numbers on the site change yet: the memory is empty until reviewers send labels.

## Website update — 2026-11-18
- New blind labelling page (`label.html`, linked from the Accuracy tab: "Start labelling stories"): outside reviewers read the 300 motor-vehicle/helmet test stories or the 240 e-bike/e-moto test stories and choose answers without seeing NEISS-AI's answers (the page holds only case numbers and stories; `scripts/build_label_sets.py`). Progress is saved in the browser; the reviewer downloads a CSV and emails it. `validation/score_human_labels.py` scores it against NEISS-AI and the existing answer key (agreement, 95% CI, Cohen's kappa, list of disagreements).
- New "See how NEISS-AI reads a story" (How it works tab; link: `#reads`): real e-bike injury stories with the matched words highlighted and the four decisions explained (device, e-bike or e-moto, helmet, motor vehicle). For pre-2024 stories decided by the classifier, a bar chart shows the words that pushed the decision and by how much. Built by `scripts/build_explainer.py` with the new `neissai.explain` module, which uses the tool's own rules and model weights; every explanation is checked against the tool's own label (new tests in `tests/test_explain.py`), and the monthly refresh rebuilds it.
- Overview: new story band at the top with two facts worked out from the national estimates: how often someone goes to an emergency department after an e-bike (and e-scooter) injury ("every 5 minutes", with the range from the 95% confidence interval and a note that it is a yearly average, not a live count), and the share of injured e-bike riders who are children, shown as 20 figures.
- Overview: new "Play 2019 → 2025" button draws the device chart one year at a time with a running caption, ending with the e-bike change since 2019 (and a note that the 2019 figure rests on few records). The axes stay fixed so years compare fairly; users who prefer reduced motion see the final chart at once.
- Your state: the map now has a title naming the device and year it shows, and the matching number box is outlined ("shown on the map"), so the map is not confused with the other two boxes.
- New "Accuracy" tab: one report card for every check in NEISS-AI (national e-bike totals vs CPSC's published figures, the e-bike/moped classifier, the e-bike/e-moto rule, motor vehicle and helmet reading, Hazard Watch back-testing, and how uncertainty is handled), with links to the methods notes and test files. It says plainly who made the answer keys (independent AI reviewers, not yet human experts), lists the known limits, and invites injury researchers to label the test stories blind ("Offer to help"). The "How it works" accuracy section now points to the new tab, and the header links to it.
- Your state: real US map with state outlines (default), with labelled call-out boxes for the small eastern states (VT, NH, MA, RI, CT, NJ, DE, MD, DC) so they are easy to tap; the square grid stays available as "Grid (easier to tap)". Map shapes from us-atlas (US Census Bureau cartographic boundaries, ISC license).
- New "Your state" tab: pick a state (or click it on the map) to see about how many e-bike, e-scooter and bicycle emergency department visits it would have if it matched the national pattern, for 2020-2025. Expected visits = national estimate x the state's share of the US population (US Census Bureau Vintage 2025, NST-EST2025-POP; states add up exactly to the US total). Clearly labelled as estimates, not counts, because NEISS has no state information. Includes a tile map, a copy-ready sentence for reports, a link to each state's view, a table for every state with CSV download, and a custom-analysis request.
- Data pack: new "Expected by state" sheet with the same numbers.
- Ask: questions that name a state now point to the Your state tab.

## Website update — 2026-11-17 (5)
- "Used NEISS-AI? Tell me": the How it works section now invites people who used the numbers in a report, grant, safety plan, presentation, class or news story to send the link or title. The button opens an email with short fields already filled in (including whether the use may be mentioned on the site). The Cite section links to it, and every one-page report now ends with a short "Used these numbers in your work? Please tell me" line.

## Website update — 2026-11-17 (4)
- The "Get the free data pack" button is now live (Overview and How it works). It opens a short sign-up form; the data pack link and the citation arrive by email within a minute.

## Website update — 2026-11-17 (3)
- Citation: the website, press page, BibTeX/RIS files, README, notebook and data pack now all cite NEISS-AI the same way, with the main DOI https://doi.org/10.5281/zenodo.23306744, which always resolves to the latest version, so every citation counts together.
- Hazard Watch: a note explains why its 2025 e-bike number (102,600, counted by CPSC's e-bike product code) differs by about 1% from the Overview (101,600, from NEISS-AI's reading of each injury story).

## Website update — 2026-11-17 (2)
- New: **one-page report (PDF)** for any Explore view and any Ask answer. It opens a print-ready page with the key numbers, the chart (always in light colours), a compact table (each cell is the estimate with its 95% confidence interval), a short "what these numbers mean" note and the citation with a link back to the exact view; "Print / Save as PDF" saves it. The title can be edited before printing. Fits on one US Letter page and works on phones, tablets and computers.

## Website update — 2026-11-17
- New: **Request a free custom analysis.** A short call-to-action on the Overview ("Need numbers for a report, grant, presentation or news story?") with buttons to Ask a question, Explore the data or request a custom analysis; a request box under every Explore view and every Ask answer; and a "Request a free custom analysis" section in How it works (what can and cannot be answered from NEISS). The request opens an email with the current view or question and a link already filled in.
- New: Explore now shows a citation line for the current view, with a "Copy citation" button.
- New: **free data pack** (`docs/NEISS-AI_DataPack.xlsx`): the website's main national estimates in one Excel file (visits by device, age group and month; hospital stays; e-bike vs e-moto; latest Hazard Watch signals), with 95% confidence intervals and the citation and DOI link at the top of every sheet. Built by `scripts/build_data_pack.py`; the monthly refresh rebuilds it when a new NEISS year arrives (the refresh job now installs openpyxl). Visitors can get it by email through a short sign-up form (optional; every number stays free on the website).

## Website update — 2026-11
- New: CDC age groups (5–9, 10–14, 15–19) and tween/teen groups (11–14, 15–17) in the Explore tab's Age menu. Children's numbers can now be compared directly with CDC injury reports and with school-age groups. Any other age range still works in "Ask a question" (for example "e-bike injuries ages 10 to 14 in 2025").
- Fix: the CPSC micromobility report (2017–2024) is now dated correctly as April 2026.

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
