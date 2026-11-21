"""Build one 'Compare your state' Excel workbook per state (docs/benchmarks/).

For state health departments and transport agencies that have their own emergency department
data: national NEISS-AI visit rates per 100,000 by 7 age groups (with 95% ranges), the state's
benchmark visits by age group (national rate x the state's population in that age group), an empty
column for the state's own count, and a ratio column (own count / benchmark) that fills itself in.

Benchmarks are not counts: NEISS has no patient-state field. Same estimator as
scripts/build_state_estimates.py (Taylor linearization, hospitals as clusters within strata).

    python scripts/build_state_benchmarks.py [--year 2025]
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from neissai.state import AGE_GROUPS, StateEstimator, load_age_population, us_population  # noqa: E402

DOCS = ROOT / "docs"
MODEL = ROOT / "src" / "neissai" / "model"
OUT = DOCS / "benchmarks"
DEVICES = ["E-bike", "E-scooter", "Bicycle"]
CITE = "Source: NEISS-AI (Kumar, 2026), https://doi.org/10.5281/zenodo.23306744 - data: US CPSC NEISS"


def unstable(n, est, se):
    cv = se / est if est > 0 else float("nan")
    return bool(n < 20 or est < 1200 or (not math.isnan(cv) and cv > 0.33))


def national_by_age(records, year, us):
    """{device: [ {est, lo, hi, records, unstable, pop, rate, rate_lo, rate_hi} per age group ]}"""
    out = {}
    g = len(AGE_GROUPS)
    for dev in DEVICES:
        se = StateEstimator(records, dev, year)
        rows = []
        for k in range(g):
            f = [0.0] * g
            f[k] = 1.0
            e = se.estimate(f)
            pop = us[k]
            rows.append({"est": e["est"], "lo": e["lo"], "hi": e["hi"], "records": se.N[k],
                         "unstable": unstable(se.N[k], e["est"], e["se"]), "pop": pop,
                         "rate": e["est"] / pop * 1e5, "rate_lo": e["lo"] / pop * 1e5, "rate_hi": e["hi"] / pop * 1e5})
        tot = se.estimate([1.0] * g)
        out[dev] = {"groups": rows, "total": tot, "records": se.records}
    return out


def _deterministic(path: Path, stamp=(2026, 1, 1, 0, 0, 0)):
    """Rewrite the xlsx zip with fixed timestamps so rebuilds give identical files."""
    src = zipfile.ZipFile(io.BytesIO(path.read_bytes()))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in sorted(src.infolist(), key=lambda i: i.filename):
            zi = zipfile.ZipInfo(info.filename, date_time=stamp)
            zi.compress_type = zipfile.ZIP_DEFLATED
            data = src.read(info.filename)
            if info.filename == "docProps/core.xml":   # openpyxl stamps the save time here
                import re
                data = re.sub(rb"(<dcterms:(?:created|modified)[^>]*>)[^<]*", rb"\g<1>2026-01-01T00:00:00Z", data)
            dst.writestr(zi, data)
    path.write_bytes(buf.getvalue())


def workbook(abbr, name, year, nat, state_pop, updated, path):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from datetime import datetime
    wb = Workbook()
    ws = wb.active
    ws.title = "Compare"
    bold, thin = Font(bold=True), Side(style="thin", color="BBBBBB")
    ws["A1"] = f"Compare your state: {name}, {year}"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = (f"Benchmark = the number of emergency department visits {name} would have if it matched the US rate "
                f"in each age group. Type your own count in the yellow column I; column J then compares it with the benchmark.")
    ws["A3"] = (f"Benchmarks are estimates from national data, not counts of visits in {name}: NEISS does not record the "
                f"patient's state. See the 'How to use' sheet for a worked example.")
    ws["A4"] = CITE + f" (data updated {updated})"
    for r in (2, 3, 4):
        ws.cell(r, 1).font = Font(size=9, color="555555")
    head = ["Device", "Age group", "US visits per 100,000 people", "US rate, 95% range: low", "US rate, 95% range: high",
            f"{name} population, {year}", f"Benchmark: visits in {name} at the US rate", "Benchmark: 95% range (low - high)",
            "Your own count (type here)", "Ratio: your count / benchmark", "Injury notes behind the US rate",
            "Few notes? (read with care)"]
    hr = 6
    for c, h in enumerate(head, 1):
        cell = ws.cell(hr, c, h)
        cell.font = bold
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        cell.fill = PatternFill("solid", fgColor="EEF3FB")
        cell.border = Border(bottom=thin)
    r = hr + 1
    groups = [g[2] for g in AGE_GROUPS]
    for dev in DEVICES:
        first = r
        for k, gname in enumerate(groups):
            n = nat[dev]["groups"][k]
            sp = state_pop[k]
            exp, lo, hi = n["rate"] * sp / 1e5, n["rate_lo"] * sp / 1e5, n["rate_hi"] * sp / 1e5
            vals = [dev, gname, round(n["rate"], 1), round(n["rate_lo"], 1), round(n["rate_hi"], 1), sp,
                    round(exp), f"{round(lo):,} - {round(hi):,}", None, f'=IF(I{r}="","",I{r}/G{r})',
                    n["records"], "yes" if n["unstable"] else "no"]
            for c, v in enumerate(vals, 1):
                ws.cell(r, c, v)
            ws.cell(r, 9).fill = PatternFill("solid", fgColor="FFF8E1")
            r += 1
        # all ages row: expected = sum of the groups (age-adjusted state estimate)
        t = nat[dev]["total"]
        ws.cell(r, 1, dev).font = bold
        ws.cell(r, 2, "All ages").font = bold
        ws.cell(r, 3, round(t["est"] / sum(nat[dev]["groups"][k]["pop"] for k in range(len(groups))) * 1e5, 1)).font = bold
        ws.cell(r, 6, f"=SUM(F{first}:F{r - 1})").font = bold
        ws.cell(r, 7, f"=SUM(G{first}:G{r - 1})").font = bold
        ws.cell(r, 9, f'=IF(COUNT(I{first}:I{r - 1})=0,"",SUM(I{first}:I{r - 1}))').font = bold
        cnt = f"COUNT(I{first}:I{r - 1})"
        ws.cell(r, 10, f'=IF({cnt}=0,"",IF({cnt}<{len(groups)},"fill in all age groups",I{r}/G{r}))').font = bold
        ws.cell(r, 11, nat[dev]["records"]).font = bold
        for c in range(1, 13):
            ws.cell(r, c).border = Border(bottom=thin)
        r += 2
    widths = [11, 10, 13, 11, 11, 14, 16, 16, 14, 13, 13, 12]
    for c, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(c)].width = w
    for col in "FG":
        for row in ws.iter_rows(min_row=hr + 1, max_row=r, min_col=ord(col) - 64, max_col=ord(col) - 64):
            for cell in row:
                cell.number_format = "#,##0"
    for row in ws.iter_rows(min_row=hr + 1, max_row=r, min_col=10, max_col=10):
        for cell in row:
            cell.number_format = "0.00"
    ws.freeze_panes = ws.cell(hr + 1, 3)
    h = wb.create_sheet("How to use")
    k = [g[2] for g in AGE_GROUPS].index("25-44")
    ex = nat["E-bike"]["groups"][k]
    sp = state_pop[k]
    bench = ex["rate"] * sp / 1e5
    blo, bhi = ex["rate_lo"] * sp / 1e5, ex["rate_hi"] * sp / 1e5
    mine = max(10, int(round(bench * 1.2 / 10.0)) * 10)
    all_e = sum(g["rate"] * state_pop[j] / 1e5 for j, g in enumerate(nat["E-bike"]["groups"]))
    lines = [
        ("How to use this table", True),
        ("1. Count your own emergency department visits for each device and age group in the same year, using your usual case definition (for example syndromic surveillance or hospital discharge data).", False),
        ("2. Type each count into the yellow column I on the Compare sheet. The All ages row adds up your counts; its ratio appears once all age groups are filled in.", False),
        ("3. Column J shows your count divided by the benchmark. 1.0 means your state matches the US rate for its age mix; 1.5 means 50% more visits than the benchmark; 0.5 means half.", False),
        ("4. Use the 95% range in column H to judge differences: a count inside the range is consistent with the US rate.", False),
        ("", False),
        (f"How the numbers are made: a worked example (e-bike, ages 25-44, {name}, {year})", True),
        (f"Step 1. About 100 US hospitals report every emergency department visit to CPSC (the NEISS sample). NEISS-AI reads each short injury note and decides the device. In {year} it found {ex['records']:,} e-bike visits for ages 25-44 in those hospitals.", False),
        (f"Step 2. Each sample visit stands for many visits across the country (CPSC gives every record a weight). Adding up the weights gives about {round(ex['est'], -2):,.0f} e-bike emergency department visits in the US for ages 25-44.", False),
        (f"Step 3. The US has about {ex['pop'] / 1e6:.1f} million people aged 25-44 (US Census Bureau). {round(ex['est'], -2):,.0f} / {ex['pop'] / 1e6:.1f} million x 100,000 = {ex['rate']:.1f} visits per 100,000 people (column C).", False),
        (f"Step 4. {name} has about {sp:,} people aged 25-44 (column F). {ex['rate']:.1f} x {sp:,} / 100,000 = about {round(bench):,} visits: the benchmark (column G).", False),
        (f"Step 5. The US number comes from a sample of hospitals, so it has a margin of error. The US rate could be as low as {ex['rate_lo']:.1f} or as high as {ex['rate_hi']:.1f} per 100,000, so the {name} benchmark range is {round(blo):,} to {round(bhi):,} (column H).", False),
        (f"Step 6. The same is done for all {len(AGE_GROUPS)} age groups and added up: about {round(all_e):,} e-bike visits for {name} at the US rate. Working by age group makes the benchmark fair for a state whose population is younger or older than the US.", False),
        (f"Step 7. If your team counted {mine:,} visits for this row, the ratio would be {mine:,} / {round(bench):,} = {mine / round(bench):.2f}: about {abs(mine / round(bench) - 1) * 100:.0f}% {'more' if mine >= bench else 'fewer'} than the benchmark. That count is {'inside' if blo <= mine <= bhi else 'outside'} the 95% range. (Example only, not real {name} data.)", False),
        ("In one sentence: US rate for each age group x the state's population in that age group = the number of visits the state would have at the US rate.", False),
        ("", False),
        ("Read with care", True),
        ("- Benchmarks come from national data (NEISS, about 100 hospitals) and the state's population by age. They are not counts of visits in the state.", False),
        ("- Differences can come from how much people ride, local roads, weather and rules, and from differences between your case definition and NEISS-AI's (device read from product codes and the injury note; e-motos counted separately).", False),
        ("- Rows marked 'yes' in column L rest on few injury notes (fewer than 20 notes, a US estimate under 1,200, or a large margin of error). CPSC advises not to rely on such estimates.", False),
        ("- US visits include everyone hurt in an incident involving the device, as on the NEISS-AI website.", False),
        ("", False),
        ("Method", True),
        ("US visits per age group: NEISS sample weights added up for visits NEISS-AI labels as each device. Rate = US visits / US population in that age group x 100,000 (US Census Bureau, Vintage 2025, July 1). Benchmark = rate x the state's population in that age group / 100,000. 95% ranges reflect the uncertainty from sampling hospitals.", False),
        ("Technical note for analysts: design-based variance by Taylor linearization, with hospitals (PSUs) as clusters within NEISS strata; the same estimator as the NEISS-AI website.", False),
        ("", False),
        ("How to cite", True),
        (CITE, False),
        ("Questions or a custom analysis: Subash Kumar, nivi05subhash@gmail.com, https://subash28kumar.github.io/neiss-ai/", False),
    ]
    for i, (t, b) in enumerate(lines, 1):
        c = h.cell(i, 1, t)
        c.font = Font(bold=b, size=12 if b else 10)
        c.alignment = Alignment(wrap_text=True, vertical="top")
    h.column_dimensions["A"].width = 110
    stamp = datetime(2026, 1, 1)
    wb.properties.created = stamp
    wb.properties.modified = stamp
    wb.properties.creator = "NEISS-AI"
    wb.save(path)
    _deterministic(path)


def main(year: int | None = None):
    records = json.loads((DOCS / "data" / "records.json").read_text(encoding="utf-8"))
    pop = load_age_population(MODEL / "state_population_age.csv")
    names = {r["abbr"]: r["state"] for r in csv.DictReader((MODEL / "state_population.csv").open(encoding="utf-8"))}
    year = year or max(y for _, y in pop if y in records["years"])
    us = us_population(pop, year)
    nat = national_by_age(records, year, us)
    OUT.mkdir(parents=True, exist_ok=True)
    updated = records.get("updated", "")
    abbrs = sorted({a for a, y in pop if y == year})
    for a in abbrs:
        workbook(a, names[a], year, nat, pop[(a, year)], updated, OUT / f"NEISS-AI_Compare_Your_State_{a}_{year}.xlsx")
    print(f"wrote {len(abbrs)} workbooks to {OUT}")
    return nat


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int)
    main(ap.parse_args().year)
