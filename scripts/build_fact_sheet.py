"""Build the one-page national e-bike fact sheet (PDF) from the site's own data.

Replaces the hand-made October 2026 fact sheet so its numbers always match the website:
every number is computed here from docs/data.json and docs/data/records.json, and the
citation uses the same concept DOI as the rest of the site.

Run: python3 scripts/build_fact_sheet.py   (also run by update_site.py on every refresh)
Output: docs/NEISS-AI_FactSheet1_Ebike_Injuries_US_2019-2025.pdf
"""
from __future__ import annotations

import datetime as _dt
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT / "src"))
from neissai.estimate import proportion  # noqa: E402

_spec = importlib.util.spec_from_file_location("build_state_briefs", ROOT / "scripts" / "build_state_briefs.py")
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)
plt, canvas, letter, HexColor = B.plt, B.canvas, B.letter, B.HexColor

OUT = DOCS / "NEISS-AI_FactSheet1_Ebike_Injuries_US_2019-2025.pdf"
CITE = ("Kumar S. NEISS-AI: AI-assisted national injury estimates from NEISS emergency department "
        "narratives [software]. Zenodo; 2026. " + B.DOI)


def records_frame() -> pd.DataFrame:
    r = json.loads((DOCS / "data" / "records.json").read_text())
    return pd.DataFrame({
        "year": [r["years"][y] for y in r["y"]], "device": [r["devices"][d] for d in r["d"]],
        "Sex": r["s"], "Body_Part": r["b"], "Body_Part_2": r["b2"], "Diagnosis": r["g"], "Diagnosis_2": r["g2"], "Disposition": r["p"],
        "PSU": r["c"], "Stratum": [r["strata"][r["cluster_stratum"][c]] for c in r["c"]], "Weight": r["w"],
    })


def share(df, den, num) -> dict:
    p = proportion(df, num, den)
    return {k: round(100 * p[k]) for k in ("share", "ci_low", "ci_high")}


def main() -> Path:
    D = json.loads((DOCS / "data.json").read_text())
    rows = {(x["year"], x["device"]): x for x in D["by_device"]}
    years = sorted({x["year"] for x in D["by_device"]})
    y1, y0, y22 = years[-1], years[-2], 2022
    eb = {y: rows[(y, "E-bike")] for y in years}
    age = {(x["year"], x["age_group"]): x for x in D["by_age"] if x["device"] == "E-bike"}

    df = records_frame()
    recent = df["year"].isin([y0, y1])
    ebm = recent & (df["device"] == "E-bike")
    bim = recent & (df["device"] == "Bicycle")
    hosp = df["Disposition"].isin([2, 4, 5, 8])   # same definition as the website: transferred, admitted, held, died
    male = share(df, ebm, df["Sex"] == 1)
    # Same rule as the website's Explore filters: the first OR the second body part / diagnosis.
    head = share(df, ebm, df["Body_Part"].isin([75, 76, 77, 88, 94]) | df["Body_Part_2"].isin([75, 76, 77, 88, 94]))
    frac = share(df, ebm, (df["Diagnosis"] == 57) | (df["Diagnosis_2"] == 57))
    h_eb, h_bi = share(df, ebm, hosp), share(df, bim, hosp)

    updated = _dt.date.fromisoformat(D["updated"])
    month = updated.strftime("%B %Y").upper()
    c = canvas.Canvas(str(OUT), pagesize=letter, invariant=1)
    W, H = letter
    m = 46
    c.setTitle("E-bike injuries in the United States, 2019-2025 (NEISS-AI fact sheet)")
    c.setAuthor("Subash Kumar")
    c.setFillColor(HexColor(B.INK3)); c.setFont("Sans-Bold", 8)
    c.drawString(m, H - 40, f"NEISS-AI FACT SHEET 1 · {month}")
    c.setFillColor(HexColor(B.INK)); c.setFont("Sans-Bold", 18)
    c.drawString(m, H - 64, f"E-bike injuries in the United States, {years[0]}–{y1}")
    y = B.para(c, m, H - 80, "National estimates of emergency department (ED) visits, from the US Consumer Product Safety "
               "Commission's National Electronic Injury Surveillance System (NEISS)", W - 2 * m, size=9, color=B.INK2)

    # three headline numbers
    tiles = [(B.fmt(eb[y1]["est"]), f"estimated ED visits for e-bike injuries in {y1} (95% CI {B.fmt(eb[y1]['lo'])}–{B.fmt(eb[y1]['hi'])})"),
             (f"+{round(100 * (eb[y1]['est'] / eb[y0]['est'] - 1))}%", f"increase from {y0} ({B.fmt(eb[y0]['est'])} visits)"),
             (f"{eb[y1]['est'] / eb[y22]['est']:.1f}×", f"the {y22} level ({B.fmt(eb[y22]['est'])} visits)")]
    tw = (W - 2 * m - 24) / 3
    ty = y - 14
    for i, (big, small) in enumerate(tiles):
        x = m + i * (tw + 12)
        c.setFillColor(HexColor(B.SURF2)); c.roundRect(x, ty - 62, tw, 62, 6, stroke=0, fill=1)
        c.setFillColor(HexColor(B.C_EBIKE)); c.setFont("Sans-Bold", 20); c.drawString(x + 10, ty - 26, big)
        B.para(c, x + 10, ty - 36, small, tw - 20, size=7.6, color=B.INK2)
    y = ty - 76

    # trend chart with likely-range band; hollow points for unstable years
    fig, ax = plt.subplots(figsize=(7.2, 2.3))
    xs = years
    est = [eb[v]["est"] for v in xs]
    ax.fill_between(xs, [eb[v]["lo"] for v in xs], [eb[v]["hi"] for v in xs], color=B.C_EBIKE, alpha=0.15, linewidth=0)
    ax.plot(xs, est, color=B.C_EBIKE, linewidth=2)
    for v in xs:
        unst = eb[v]["unstable"]
        ax.plot([v], [eb[v]["est"]], "o", markersize=5, markerfacecolor="white" if unst else B.C_EBIKE,
                markeredgecolor=B.C_EBIKE, markeredgewidth=1.5)
    ax.set_xticks(xs); ax.set_ylim(bottom=0)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v / 1000:.0f}k"))
    ax.grid(axis="y", color=B.BORDER, linewidth=0.6)
    img = B.png(fig)
    ch = 150
    c.drawImage(img, m, y - ch, width=W - 2 * m, height=ch, preserveAspectRatio=True, anchor="w")
    unst_years = [str(v) for v in xs if eb[v]["unstable"]]
    y = B.para(c, m, y - ch - 4, "Estimated US ED visits for e-bike injuries; the shaded band is the 95% confidence interval. "
               + (f"Hollow points ({', '.join(unst_years)}) rest on few records (CPSC's rule), so read them with care."
                  if unst_years else ""), W - 2 * m, size=7.4, color=B.INK2) - 8

    c.setFillColor(HexColor(B.INK)); c.setFont("Sans-Bold", 10.5)
    c.drawString(m, y, f"Who is injured and how ({y0}–{y1} combined)"); y -= 15
    o65 = (age[(y22, "65+")]["est"], age[(y1, "65+")]["est"])
    y = B.bullets(c, m, y, [
        f"Mostly men: about {male['share']}% of injured riders were male (95% CI {male['ci_low']}–{male['ci_high']}%).",
        f"Head and face: about {head['share']}% of visits included an injury to the head or face (95% CI {head['ci_low']}–{head['ci_high']}%).",
        f"Broken bones: about {frac['share']}% of visits included a fracture (95% CI {frac['ci_low']}–{frac['ci_high']}%).",
        f"Hospital stays: about {h_eb['share']}% of e-bike visits (95% CI {h_eb['ci_low']}–{h_eb['ci_high']}%) ended in a hospital stay "
        f"(admitted, transferred or held; the rare deaths in the ED included); for bicycle injuries the share was {h_bi['share']}% (95% CI {h_bi['ci_low']}–{h_bi['ci_high']}%).",
        f"Older riders: visits among adults 65 and older rose from about {B.fmt(o65[0])} in {y22} to {B.fmt(o65[1])} in {y1}.",
    ], W - 2 * m, size=8.4) - 6

    c.setFillColor(HexColor(B.ACCENT_SOFT)); box_top = y
    text = ("Is the rise just a change in coding? No. CPSC gave e-bikes their own product code in 2024, and both 2024 and "
            "2025 use that code, so the 2024–2025 rise is not a coding effect. For 2019–2023, when e-bikes shared a code with "
            "mopeds, NEISS-AI reads the injury stories to tell them apart; unclear notes are decided by a text model, so "
            "those early years are less certain.")
    lines = B.wrap(c, text, "Sans", 8.2, W - 2 * m - 20)
    bh = 12 + 11.4 * len(lines)
    c.roundRect(m, box_top - bh, W - 2 * m, bh, 6, stroke=0, fill=1)
    B.para(c, m + 10, box_top - 14, text, W - 2 * m - 20, size=8.2)
    y = box_top - bh - 20

    c.setFillColor(HexColor(B.INK)); c.setFont("Sans-Bold", 10.5); c.drawString(m, y, "About these estimates"); y -= 15
    y = B.bullets(c, m, y, [
        "NEISS is a national probability sample of about 100 US hospital EDs. Estimates use CPSC's survey weights and design, "
        "with 95% confidence intervals.",
        "NEISS-AI identifies e-bikes from product codes and the written injury stories. National e-bike totals for 2022–2024 "
        "are within 5% of CPSC's published figures (CPSC, April 2026).",
        "Limits: these are counts of ED visits, not injury rates; the number of riders is not known. Only ED-treated injuries "
        "are included. These are national numbers; the state numbers on the website are expected numbers, not counts.",
    ], W - 2 * m, size=8.2) - 4

    B.para(c, m, 74, "Cite as: " + CITE, W - 2 * m, size=7.4, color=B.INK2)
    B.para(c, m, 50, f"Explore the data and download tables: {B.SITE} · Free and open source · Numbers updated {D['updated']} "
           "(NEISS-AI " + D["version"] + ") · Prepared by Subash Kumar, Independent Researcher, Ellicott City, Maryland. "
           "An independent project, not affiliated with or endorsed by CPSC.", W - 2 * m, size=7.2, color=B.INK3)
    c.showPage(); c.save()
    print(f"wrote {OUT}")
    return OUT


if __name__ == "__main__":
    main()
