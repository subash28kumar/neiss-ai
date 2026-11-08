# Emerging-hazard scan: how it works (methods note, DRAFT)

The scan (`neissai.hazards`, `neissai hazards` on the command line) looks at every product
code in the US NEISS emergency department sample and asks one question:

> **Did injuries linked to this product rise this year by more than all of NEISS rose?**

It is a screening tool. A flag means "a person should look at this", not "this product became
more dangerous".

## What I compare

- **Two measures, kept separate:** emergency department (ED) visits, and hospital admissions
  (the admitted/hospitalized subset of those visits).
- **A year against the year before** (for example 2025 against 2024). The same code can compare
  the same months of two years (for example January–June), for a part-year check.
- **National numbers.** Each NEISS record carries a weight (how many US visits it stands for).
  I add up the weights. The numbers match NEISS-AI's own national totals: for bicycles
  (code 5040) in 2025 the scan gives 420,962 visits with a standard error of 38,649, the same
  as `neissai.total` on the full CPSC file.
- **Data:** the full CPSC NEISS files for 2019–2025 (2,442,011 records), summarised by product,
  month and hospital (`clusters.csv`; the published tables were made in Colab, and
  `neissai hazard-export` makes the same tables from the downloaded files), plus the list of every hospital in the
  sample each year (`psu.csv`) and word counts from the injury stories (`terms.csv`).

## The checks, in plain words

1. **"Excess" rise, not raw rise.** If all of NEISS went up 18%, a product that went up 18%
   has not changed. I first work out what a product would be if it had simply moved with all
   of NEISS, and measure only the rise above that ("excess"). Admissions are compared with all
   admissions, ED visits with all ED visits.
2. **Is the rise bigger than chance?** NEISS is a sample of about 80 hospitals (77–84 each year), so every
   number has sampling error. I estimate that error the way CPSC does (hospitals as clusters
   within strata, including hospitals with zero cases of that product). Because the same
   hospital usually takes part in both years, the comparison uses each hospital's own
   year-to-year difference.
3. **Many products at once.** Testing about 800 products means some will look unusual by luck.
   I control the false discovery rate at 5% (Benjamini–Hochberg): among flagged products, no
   more than about 1 in 20 should be false alarms.
4. **Big enough to detect.** For each product I report the minimum detectable change: the
   smallest excess rise the data could pick up 80% of the time. A flag also needs the rise to be
   at least that large.
5. **CPSC's reporting rule.** The current year's estimate must not be "unstable" (fewer than
   20 records, fewer than 1,200 estimated visits, or a coefficient of variation above 33%).
6. **Product code changes.** CPSC sometimes splits or replaces codes. When a code changes
   between the two years being compared, I combine the old and new codes into one group so
   the comparison is like with like: e-bikes and mopeds (3215 became 5045 and 5046 in 2024),
   scooters and hoverboards (1329 and 5042 became 5022–5025 in 2020), and cribs (1543 and 1545
   became 1552 in 2021). The groups are used **only** for comparisons that cross the change;
   2025 against 2024 compares 5045 on its own. The scan also finds code changes by itself (a
   code that appears from nothing with at least 20 records, or vanishes). On the 2019–2025 data
   it found exactly these three changes and no others. A new code is never flagged as a hazard.
7. **One-hospital check.** For every flag I report how much of the excess comes from the single
   biggest hospital. If it is more than half, the note says to check coding at that hospital.

## New words in the injury stories

Hazards can appear in the stories before CPSC has a code for them. I compare how often each
word or word pair appears with how many records there are. I use two tests: a simple count test
(Poisson), and a stricter one that allows for the normal year-to-year drift in word use, which is
large in NEISS because the people who write the stories change. A word must pass both, rise at
least 1.5 times faster than the records, and appear at least 20 times.

Many rising words are about **how** stories are written, not **what** happened: PT, YOM, DX,
STATED, PRESENTS, "LWBS", new spellings and typos. I filter these out with a list of charting
words and abbreviations, a check for one-letter typos of common words, and a list of body,
diagnosis, place and family words. The list still needs a person to read it. In every year
there are over 100 words left (121 in 2023, 630 in 2024).

The word check passes a retrospective test: "ELECTRIC BIKE" and "ELECTRIC SCOOTER" are
flagged in 2021, "E-BIKE" and "ELECTRIC BICYCLE" in 2022, "E-BIKE" again in 2023 (all before
CPSC's 2024 e-bike code), "WATER BEADS" in 2023, "E-SCOOTER" in 2024, and "E-BIKE" and
"ELECTRIC BICYCLE" in 2025. "COVID" is the top new word in 2020.

## Labels on the results

- **2020 and 2021: "pandemic years, interpret with caution".** Injury patterns changed sharply
  (less sport and school, more home and outdoor activity, then a rebound), so many products are
  flagged: 33 for ED visits in 2020 and 27 in 2021. 2022 is labelled too, because it is compared
  with a pandemic year.
- **2024: why there are no flags.** NEISS weights rose about 18% in 2024 (all-NEISS weighted
  visits 12.74 million in 2023, 15.07 million in 2024, while records rose only 7%). The rise was
  uneven: stratum S +27%, stratum V +46%, stratum M −6%, and CPSC moved hospitals between strata.
  The excess check removes the general rise, but the uneven change adds noise, and the minimum
  detectable changes are larger than in other years (median 36% for ED visits and 52% for
  admissions, against 34–35% and 45–49% in 2021–2023). The strongest 2024 rise did not pass the
  false-discovery check. "No flags in 2024" means "this year's data could not show it", not
  "nothing rose".
- **Floors (1807) in 2025: "likely coding practice; label pending check".** Floor-related
  visits jumped from about 1.86 to 3.08 million. The jump starts suddenly in April 2025 and is
  seen at most hospitals (the floor share of all records rose by more than 30% at 68% of
  hospitals from April on, against 29% in January–March). A sudden, sample-wide step looks
  like a change in how cases are coded, not a new hazard. I have not confirmed this with CPSC.

## Results in brief (full tables in the output folder)

| Year | ED visit flags | Admission flags | Notes |
|---|---|---|---|
| 2020 | 33 | 1 | pandemic year |
| 2021 | 27 | 1 | pandemic year; e-scooters (5022) flagged |
| 2022 | 6 | 0 | compared with a pandemic year |
| 2023 | 3 | 0 | |
| 2024 | 0 | 0 | weights rose ~18% (see above) |
| 2025 | 5 | 1 | e-bikes 5045 (59,600 → 102,600), e-scooters 5022 (118,500 → 165,700), floors 1807 (ED and admissions; likely coding), power workshop grinders 897 (10,200 → 18,800), infant and toddler play centers 1550 (small numbers) |

**The old e-bike code.** Before 2024, e-bikes were counted with mopeds under code 3215. In the
all-product scan, 3215 is **not** flagged in any year: its yearly estimates have coefficients
of variation of 38–45% (unstable by CPSC's rule) and its rises do not pass the false-discovery
check among 800 products. When I watch 3215 on its own as a product chosen in advance
(`neissai.hazards.watch`), a one-sided test of the rise at the 5% level signals ED visits in
2021, 2022 and 2023 and admissions in 2021 and 2023, three years before CPSC created the e-bike
code. That is a fair test for a product someone is already watching. It is not a discovery
made by the all-product scan.

**The words did catch it early.** The word check flagged "electric bike" in 2021 (76 → 170
stories), "e-bike" in 2022 (27 → 121) and 2023, and both again in 2024 and 2025. So the stories
showed the rise every year from 2021, three years before CPSC's separate e-bike code. This is
how I describe the e-bike result: an early signal in the words, supported by the rise of the old
code when it is watched on its own.

## Rates

Each estimate also comes as a rate per 100,000 US residents, using the Census Bureau's July 1
population (Vintage 2025 estimates for 2020-2025; the 2010-2020 intercensal series for 2019).
For 2025: e-bikes 17.5 to 30.0, e-scooters 34.9 to 48.5, power workshop grinders 3.0 to 5.5 ED
visits per 100,000 people. The flags do not change, because the scan already compares each
product with all NEISS visits. These rates describe the burden on the population. Risk per rider,
trip or product sold needs exposure data, which I add only where a public source exists.

## Limits

- NEISS counts ED visits, not riders, products sold or hours of use, so a rise can mean more
  use, not more danger. I have not added population or sales rates yet.
- A product can be named in up to three code fields; the scan counts a record once under each
  different code it carries. A code group adds its member codes, so a record carrying two codes
  from the same group would count twice (rare).
- The word check uses counts across all hospitals, with no hospital-level detail, so it cannot
  give a design-based error. It is a screen only.
- Monthly scans are possible but much less sensitive. For 2025, the median single-month minimum
  detectable change was 50% for e-bikes (28% for the full year), 33% for e-scooters (15%) and
  14% for bicycles (6%).
- Product names come from CPSC's NEISS format file (tidied); a few long names are shortened.
- Word counts made with `neissai hazard-export` can differ slightly from the published tables,
  because the original Colab word rules were not saved.
