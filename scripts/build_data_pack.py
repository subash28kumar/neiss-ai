"""Build the free NEISS-AI data pack (docs/NEISS-AI_DataPack.xlsx) from the website data.

The pack holds the same national estimates the website shows (docs/data.json and the Hazard Watch
summary), one table per sheet, and every sheet starts with the citation and the DOI link, so the
numbers travel with their source. The file name stays the same every year, so links to it keep working.

    python scripts/build_data_pack.py            # writes docs/NEISS-AI_DataPack.xlsx

Called automatically by scripts/update_site.py after each data refresh (needs openpyxl).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUT = DOCS / "NEISS-AI_DataPack.xlsx"
SITE = "https://subash28kumar.github.io/neiss-ai/"
FONT = "Arial"


def _cff():
    """Version, DOI and title from CITATION.cff (no YAML dependency needed)."""
    txt = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    get = lambda k, d="": (re.search(rf"^{k}:\s*\"?([^\"\n]+)\"?", txt, re.M) or [None, d])[1].strip()
    return get("version", "1.6.1"), get("doi", "10.5281/zenodo.23306744"), get("title", "NEISS-AI")


VERSION, DOI, TITLE = _cff()
DOI_URL = f"https://doi.org/{DOI}"
CITATION = f"Kumar S. {TITLE} [software]. Zenodo; 2026. {DOI_URL}"   # concept DOI: same citation as the website
SOURCE_LINE = f"Source: NEISS-AI (Kumar, 2026), {DOI_URL}. Data: US Consumer Product Safety Commission, NEISS."

HDR_FILL = PatternFill("solid", fgColor="1F3864")
CITE_FILL = PatternFill("solid", fgColor="E6F0FC")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _top(ws, title, updated, ncols):
    """Rows 1-3 of every data sheet: title, citation with DOI link, data note."""
    ws["A1"] = title
    ws["A1"].font = Font(name=FONT, size=13, bold=True)
    ws["A2"] = "Please cite: " + CITATION
    ws["A2"].hyperlink = DOI_URL
    ws["A2"].font = Font(name=FONT, size=10, color="1F4E99", underline="single")
    ws["A3"] = (f"National estimates of US emergency department visits from CPSC NEISS (public data), with 95% "
                f"confidence intervals. Updated {updated}. More: {SITE}")
    ws["A3"].font = Font(name=FONT, size=9, italic=True, color="555555")
    for r in (1, 2, 3):
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=max(ncols, 6))
        ws.cell(row=r, column=1).alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[2].height = 30
    ws.row_dimensions[3].height = 26
    for c in range(1, max(ncols, 6) + 1):
        ws.cell(row=2, column=c).fill = CITE_FILL


def _table(ws, headers, rows, formats, widths, start=5):
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=start, column=c, value=h)
        cell.font = Font(name=FONT, bold=True, color="FFFFFF")
        cell.fill = HDR_FILL
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        cell.border = BORDER
    for i, row in enumerate(rows, 1):
        for c, v in enumerate(row, 1):
            cell = ws.cell(row=start + i, column=c, value=v)
            cell.font = Font(name=FONT, size=10)
            cell.border = BORDER
            if formats.get(c):
                cell.number_format = formats[c]
    for c, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.freeze_panes = ws.cell(row=start + 1, column=1)
    ws.auto_filter.ref = f"A{start}:{get_column_letter(len(headers))}{start + len(rows)}"
    note = start + len(rows) + 2
    ws.cell(row=note, column=1, value="Unstable = yes: fewer than 20 NEISS records, an estimate under 1,200, or a "
                                       "coefficient of variation over 33% (CPSC's rule). Treat these numbers as rough.")
    ws.cell(row=note + 1, column=1, value=SOURCE_LINE)
    for r in (note, note + 1):
        ws.cell(row=r, column=1).font = Font(name=FONT, size=9, italic=True, color="555555")


def build(out: Path = OUT) -> Path:
    data = json.loads((DOCS / "data.json").read_text(encoding="utf-8"))
    updated = data.get("updated", "")
    yn = lambda b: "yes" if b else "no"
    wb = Workbook()

    # ---- Read me
    ws = wb.active
    ws.title = "Read me"
    yrs = sorted({r["year"] for r in data["by_device"]})
    span = f"{yrs[0]}-{yrs[-1]}" if yrs else ""
    lines = [
        (f"NEISS-AI data pack: US e-bike, e-scooter and bicycle injuries, {span}", "title"),
        ("", None),
        ("How to cite (please include this whenever you use these numbers)", "head"),
        (CITATION, "cite"),
        ("Short source line for charts and slides:", None),
        (SOURCE_LINE, "cite"),
        ("", None),
        ("What is in this file", "head"),
        ("Visits by device: national emergency department (ED) visits per year for e-bikes, e-scooters, bicycles "
         "and other micromobility devices, with 95% confidence intervals.", None),
        ("E-bike and e-scooter by age: visits per year for children (0-17), adults (18-64) and older adults (65+).", None),
        (f"Hospital stays: share of ED visits that led to a hospital stay, by device and age group ({span} combined).", None),
        ("E-bike vs e-moto: e-bike visits split into regular e-bikes, likely e-motos and unclear stories.", None),
        ("By month: visits per month for bicycles, e-bikes and e-scooters.", None),
        ("Hazard Watch: consumer products whose ED visits rose much faster than all ED visits in the latest year.", None),
        ("", None),
        ("About the numbers", "head"),
        ("Source data: the US Consumer Product Safety Commission's National Electronic Injury Surveillance System "
         "(NEISS), a national probability sample of about 100 hospital emergency departments. CPSC does not "
         "endorse NEISS-AI.", None),
        ("Method: NEISS-AI labels each injury record with a text classifier and rules (so e-bike counts stay "
         "consistent across CPSC's 2024 product-code change), then uses the NEISS survey weights with "
         "Taylor-linearized 95% confidence intervals. Full method and code: " + SITE, None),
        ("Limits: these are counts of ED visits, not risk rates (the number of riders is not known). NEISS has no "
         "state or city information. Early e-bike estimates (2019-2021) rest on small samples.", None),
        ("", None),
        (f"Data updated: {updated}. NEISS-AI version {VERSION}. Free to use, share and adapt with the citation above.", None),
        (f"Need a different breakdown? Request a free custom analysis: {SITE}#about", None),
        ("Built by Subash Kumar, independent researcher (ORCID 0009-0003-6661-3424).", None),
    ]
    for i, (t, kind) in enumerate(lines, 1):
        c = ws.cell(row=i, column=1, value=t)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        # explicit row height so long lines show in full in Excel Online too (it does not auto-fit wrapped rows)
        if t and kind != "title":
            ws.row_dimensions[i].height = 15 * max(1, -(-len(t) // 110))
        if kind == "title":
            c.font = Font(name=FONT, size=14, bold=True)
        elif kind == "head":
            c.font = Font(name=FONT, size=11, bold=True)
        elif kind == "cite":
            c.font = Font(name=FONT, size=10, color="1F4E99", underline="single")
            c.hyperlink = DOI_URL
            c.fill = CITE_FILL
        else:
            c.font = Font(name=FONT, size=10)
    ws.column_dimensions["A"].width = 120

    # ---- Visits by device
    ws = wb.create_sheet("Visits by device")
    _top(ws, "Emergency department visits by device and year", updated, 7)
    rows = [[r["year"], r["device"], r["est"], r["lo"], r["hi"], r["n"], yn(r["unstable"])]
            for r in sorted(data["by_device"], key=lambda r: (r["device"], r["year"]))]
    _table(ws, ["Year", "Device", "Estimated visits", "95% CI low", "95% CI high", "NEISS records", "Unstable"],
           rows, {3: "#,##0", 4: "#,##0", 5: "#,##0", 6: "#,##0"}, [8, 20, 16, 13, 13, 14, 10])

    # ---- by age
    ws = wb.create_sheet("By age")
    _top(ws, "E-bike and e-scooter emergency department visits by age group and year", updated, 8)
    rows = [[r["year"], r["device"], r["age_group"], r["est"], r["lo"], r["hi"], r["n"], yn(r["unstable"])]
            for r in sorted(data["by_age"], key=lambda r: (r["device"], r["age_group"], r["year"]))]
    _table(ws, ["Year", "Device", "Age group", "Estimated visits", "95% CI low", "95% CI high", "NEISS records", "Unstable"],
           rows, {4: "#,##0", 5: "#,##0", 6: "#,##0", 7: "#,##0"}, [8, 14, 11, 16, 13, 13, 14, 10])

    # ---- hospital stays
    ws = wb.create_sheet("Hospital stays")
    _top(ws, f"Share of emergency department visits that led to a hospital stay, {span} combined", updated, 6)
    rows = [[r["device"], r["age_group"], r["share"], r["lo"], r["hi"], r["n"]]
            for r in sorted(data["hospitalized"], key=lambda r: (r["device"], r["age_group"]))]
    _table(ws, ["Device", "Age group", "Share with a hospital stay", "95% CI low", "95% CI high", "NEISS records"],
           rows, {3: "0.0%", 4: "0.0%", 5: "0.0%", 6: "#,##0"}, [14, 11, 16, 13, 13, 14])

    # ---- e-bike vs e-moto
    ws = wb.create_sheet("E-bike vs e-moto")
    _top(ws, "E-bike emergency department visits: regular e-bikes, likely e-motos and unclear stories", updated, 7)
    rows = [[r["year"], r["type"], r["est"], r["lo"], r["hi"], r["n"], yn(r["unstable"])]
            for r in sorted(data["by_ebike_type"], key=lambda r: (r["type"], r["year"]))]
    _table(ws, ["Year", "Group", "Estimated visits", "95% CI low", "95% CI high", "NEISS records", "Unstable"],
           rows, {3: "#,##0", 4: "#,##0", 5: "#,##0", 6: "#,##0"}, [8, 16, 16, 13, 13, 14, 10])

    # ---- by month
    ws = wb.create_sheet("By month")
    _top(ws, "Emergency department visits by month (bicycles, e-bikes, e-scooters)", updated, 8)
    rows = [[r["year"], r["month"], r["device"], r["est"], r["lo"], r["hi"], r["n"], yn(r["unstable"])]
            for r in sorted(data["by_month"], key=lambda r: (r["device"], r["year"], r["month"]))]
    _table(ws, ["Year", "Month", "Device", "Estimated visits", "95% CI low", "95% CI high", "NEISS records", "Unstable"],
           rows, {4: "#,##0", 5: "#,##0", 6: "#,##0", 7: "#,##0"}, [8, 8, 12, 16, 13, 13, 14, 10])

    # ---- Hazard Watch (latest year)
    hz_file = DOCS / "data" / "hazards" / "summary.json"
    if hz_file.exists():
        hz = json.loads(hz_file.read_text(encoding="utf-8"))
        ws = wb.create_sheet("Hazard Watch")
        _top(ws, f"Hazard Watch {hz.get('year')}: products whose ED visits rose much faster than all ED visits "
                 f"({hz.get('base_year')} to {hz.get('year')})", updated, 8)
        rows = [[s.get("product"), s.get("name"), s.get("before"), s.get("after"), s.get("pct"),
                 s.get("rate_before"), s.get("rate_after"), s.get("status")] for s in hz.get("signals", [])]
        _table(ws, ["CPSC code", "Product", f"Visits {hz.get('base_year')}", f"Visits {hz.get('year')}", "Change",
                    f"Per 100,000 ({hz.get('base_year')})", f"Per 100,000 ({hz.get('year')})", "Status"],
               rows, {3: "#,##0", 4: "#,##0", 5: "+0%;-0%", 6: "0.00", 7: "0.00"}, [10, 42, 14, 14, 10, 14, 14, 10])
        ws.cell(row=5 + len(rows) + 4, column=1,
                value="Status: Signal = a stable rise; Check = small numbers, read the injury stories first; "
                      "Coding = most likely a change in how cases were coded. Method: " + SITE + "#hazards"
                ).font = Font(name=FONT, size=9, italic=True, color="555555")

    for s in wb.worksheets:
        s.sheet_view.showGridLines = s.title != "Read me"
        s.page_setup.orientation = "landscape"
        s.page_setup.fitToWidth = 1
        s.page_setup.fitToHeight = 0
        s.sheet_properties.pageSetUpPr.fitToPage = True
    wb.properties.title = "NEISS-AI data pack"
    wb.properties.creator = "Subash Kumar (NEISS-AI)"
    wb.properties.subject = CITATION
    wb.save(out)
    return out


if __name__ == "__main__":
    print("wrote", build())
