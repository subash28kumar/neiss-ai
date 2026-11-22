"""Build one-page state briefs (PDF) from docs/data/state_estimates.json.

Each brief shows the state's expected emergency department visits for e-bikes, e-scooters and
bicycles (age-adjusted, with 95% ranges), the 2020-2025 trend, the e-bike age breakdown, how the
numbers were calculated, their limits, and a ready-to-use citation.

Run:  PYTHONPATH=src python scripts/build_state_briefs.py            (all 51)
      PYTHONPATH=src python scripts/build_state_briefs.py --states MA CA
Output: docs/briefs/NEISS-AI_State_Brief_<ABBR>_<YEAR>.pdf
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from reportlab.lib.colors import HexColor  # noqa: E402
from reportlab.lib.pagesizes import letter  # noqa: E402
from reportlab.lib.utils import ImageReader  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SITE = "https://subash28kumar.github.io/neiss-ai/"
DOI = "https://doi.org/10.5281/zenodo.23306744"
CONTACT = "nivi05subhash@gmail.com"

# Site palette (light mode): e-bike --s1, e-scooter --s2, bicycle --ref; text tokens.
C_EBIKE, C_ESCOOT, C_BIKE = "#2a78d6", "#eb6834", "#8a8984"
INK, INK2, INK3 = "#0b0b0b", "#52514e", "#7a7974"
BORDER, SURF2, ACCENT_SOFT = "#e2e0da", "#f0efec", "#e6f0fc"

FONT_DIR = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
pdfmetrics.registerFont(TTFont("Sans", str(FONT_DIR / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("Sans-Bold", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("Sans-Italic", str(FONT_DIR / "DejaVuSans-Oblique.ttf")))
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.edgecolor": BORDER,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "axes.spines.top": False, "axes.spines.right": False})


def fmt(v: float) -> str:
    """Round like the website: nearest 100 above 1,000, nearest 10 below."""
    v = float(v)
    half_up = lambda x: math.floor(x + 0.5)          # same as JavaScript Math.round on the website
    if v >= 1000:
        return f"{half_up(v / 100) * 100:,.0f}"
    if v >= 100:
        return f"{half_up(v / 10) * 10:,.0f}"
    return f"{half_up(v):,.0f}"


def fmt10(v: float) -> str:
    """Nearest 10, for comparing two close numbers."""
    return f"{math.floor(float(v) / 10 + 0.5) * 10:,.0f}"


def wrap(c: canvas.Canvas, text: str, font: str, size: float, width: float) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = (line + " " + word).strip()
        if c.stringWidth(trial, font, size) <= width:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def para(c, x, y, text, width, font="Sans", size=8.2, lead=None, color=INK) -> float:
    lead = lead or size * 1.38
    c.setFont(font, size)
    c.setFillColor(HexColor(color))
    for ln in wrap(c, text, font, size, width):
        c.drawString(x, y, ln)
        y -= lead
    return y


def bullets(c, x, y, items, width, size=8.2, color=INK) -> float:
    for it in items:
        c.setFillColor(HexColor(INK3))
        c.circle(x + 2.2, y + size * 0.32, 1.3, stroke=0, fill=1)
        y = para(c, x + 9, y, it, width - 9, size=size, color=color) - 2.5
    return y


def png(fig) -> ImageReader:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=300, facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return ImageReader(buf)


def trend_chart(st: dict, years: list[int], unstable: dict) -> ImageReader:
    fig, ax = plt.subplots(figsize=(3.4, 2.1))
    xs = years
    top = 0
    for dev, col in (("E-scooter", C_ESCOOT), ("E-bike", C_EBIKE)):
        e = [st["e"][dev][str(y)] for y in years]
        est, lo, hi = [r[0] for r in e], [r[1] for r in e], [r[2] for r in e]
        top = max(top, max(hi))
        ax.fill_between(xs, lo, hi, color=col, alpha=0.13, linewidth=0)
        ax.plot(xs, est, color=col, linewidth=2, solid_capstyle="round")
        for x, v in zip(xs, est):
            un = unstable[(dev, x)]
            ax.plot([x], [v], marker="o", markersize=4.2, color=col,
                    markerfacecolor="white" if un else col, markeredgewidth=1.4)
        ax.annotate(f"{dev}  {fmt(est[-1])}", xy=(xs[-1], est[-1]), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=7.6, color=INK, fontweight="bold")
    ax.set_xlim(xs[0] - 0.2, xs[-1] + 0.2)
    ax.set_ylim(0, top * 1.08)
    ax.set_xticks(xs)
    fig.subplots_adjust(left=0.13, right=0.69, bottom=0.11, top=0.97)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.grid(axis="y", color="#e9e7e2", linewidth=0.6)
    ax.tick_params(length=0, labelsize=7.2)
    ax.set_axisbelow(True)
    return png(fig)


def age_chart(st: dict, year: int, groups: list[str]) -> ImageReader:
    rows = st["age"]["E-bike"][str(year)]
    est = [r[0] for r in rows]
    lo = [r[1] for r in rows]
    hi = [r[2] for r in rows]
    fig, ax = plt.subplots(figsize=(3.4, 2.1))
    ys = list(range(len(groups)))[::-1]
    ax.barh(ys, est, height=0.62, color=C_EBIKE, edgecolor="white", linewidth=1.5)
    ax.errorbar(est, ys, xerr=[[e - l for e, l in zip(est, lo)], [h - e for e, h in zip(est, hi)]],
                fmt="none", ecolor=INK3, elinewidth=0.9, capsize=2)
    for y, e, h in zip(ys, est, hi):
        ax.text(h + max(hi) * 0.03, y, fmt(e), va="center", fontsize=7.2, color=INK)
    ax.set_yticks(ys)
    ax.set_yticklabels(groups, fontsize=7.4)
    ax.set_xlim(0, max(hi) * 1.22)
    fig.subplots_adjust(left=0.17, right=0.97, bottom=0.11, top=0.97)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.grid(axis="x", color="#e9e7e2", linewidth=0.6)
    ax.tick_params(length=0, labelsize=7.2)
    ax.set_axisbelow(True)
    return png(fig)


def age_mix_sentence(st: dict, us_pop: list[int], groups: list[str], year: int) -> tuple[str, float]:
    e = st["e"]["E-bike"][str(year)]
    adj, simple = e[0], e[3]
    diff = (adj / simple - 1) * 100 if simple else 0
    sp = st["pop"][str(year)]
    share_all = sum(sp) / sum(us_pop)
    # the age groups where the state has relatively more / fewer people than the nation
    rel = [(sp[k] / us_pop[k]) / share_all - 1 for k in range(len(groups))]
    hi_g = [groups[k] for k in (3, 4) if rel[k] > 0.02]      # 18-24, 25-44: the highest e-bike injury rates
    old = rel[6]
    if abs(diff) < 3:
        same = fmt10(adj) == fmt10(simple)
        txt = (f"Age mix: the state's age mix is close to the national one, so adjusting for age changes the "
               f"e-bike estimate by less than 3%" + ("." if same else f" (about {fmt10(adj)} vs {fmt10(simple)} "
                                                       f"from population alone)."))
    else:
        why = []
        if hi_g:
            why.append("more residents aged " + " and ".join(hi_g))
        if old > 0.05:
            why.append("more residents aged 65+")
        elif old < -0.05:
            why.append("fewer residents aged 65+")
        reason = f" (relatively {', '.join(why)} than the US)" if why else ""
        txt = (f"Age mix: adjusting for the state's age mix{reason} makes the e-bike estimate "
               f"{abs(diff):.0f}% {'higher' if diff > 0 else 'lower'} than a population-only estimate "
               f"(about {fmt10(adj)} vs {fmt10(simple)}).")
    return txt, diff


def build_one(D: dict, nat: dict, abbr: str, year: int, out: Path) -> Path:
    st = D["states"][abbr]
    name = st["name"]
    the = "the District of Columbia" if abbr == "DC" else name      # name inside a sentence
    groups = D["age_groups"]
    years = D["years"]
    us_pop = D["us"][str(year)]["pop"]
    unstable = {(r["device"], r["year"]): r["unstable"] for r in nat["by_device"]}
    W, H = letter
    M = 40
    path = out / f"NEISS-AI_State_Brief_{abbr}_{year}.pdf"
    c = canvas.Canvas(str(path), pagesize=letter, invariant=1)   # same input -> same bytes
    c.setTitle(f"NEISS-AI State Brief: {name}, {year}")
    c.setAuthor("Subash Kumar")
    c.setSubject("Expected e-bike, e-scooter and bicycle emergency department visits")

    # header band
    c.setFillColor(HexColor(C_EBIKE))
    c.rect(0, H - 34, W, 34, stroke=0, fill=1)
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Sans-Bold", 10.5)
    c.drawString(M, H - 22, "NEISS-AI  ·  State Brief")
    c.setFont("Sans", 10.5)
    c.drawRightString(W - M, H - 22, f"{name}  ·  {year}")

    y = H - 64
    y = para(c, M, y, f"E-bike, e-scooter and bicycle injuries in {the}: expected emergency department visits, {year}",
             W - 2 * M, font="Sans-Bold", size=15, lead=19)
    y = para(c, M, y - 1, "Expected numbers based on national hospital data and the state's age mix. They are estimates, "
             "not counts: the national injury data (NEISS) do not record the patient's state.", W - 2 * M,
             size=8.4, color=INK2) - 6

    # key-number tiles
    tw, gap = (W - 2 * M - 2 * 10) / 3, 10
    th = 74
    for i, (dev, col) in enumerate((("E-bike", C_EBIKE), ("E-scooter", C_ESCOOT), ("Bicycle", C_BIKE))):
        x = M + i * (tw + gap)
        e = st["e"][dev][str(year)]
        c.setFillColor(HexColor("#ffffff"))
        c.setStrokeColor(HexColor(BORDER))
        c.roundRect(x, y - th, tw, th, 6, stroke=1, fill=1)
        c.setFillColor(HexColor(col))
        c.roundRect(x, y - th, 4, th, 2, stroke=0, fill=1)
        c.setFillColor(HexColor(INK2))
        c.setFont("Sans", 7.8)
        c.drawString(x + 12, y - 15, f"Expected {dev} visits, {year}")
        c.setFillColor(HexColor(INK))
        c.setFont("Sans-Bold", 19)
        c.drawString(x + 12, y - 38, f"about {fmt(e[0])}")
        c.setFont("Sans", 7.4)
        c.setFillColor(HexColor(INK2))
        rate = e[0] / sum(st["pop"][str(year)]) * 1e5
        c.drawString(x + 12, y - 52, f"range {fmt(e[1])} to {fmt(e[2])} (national uncertainty)")
        c.drawString(x + 12, y - 63, f"{rate:,.1f} per 100,000 residents")
        c.setFillColor(HexColor(INK3))
        c.drawString(x + 12, y - 73, f"Population-only estimate: {fmt(e[3])}")
    y -= th + 16

    # key points
    c.setFont("Sans-Bold", 10)
    c.setFillColor(HexColor(INK))
    c.drawString(M, y, "Key points")
    y -= 14
    eb = st["e"]["E-bike"]
    first = 2022 if "2022" in eb else years[0]
    up = eb[str(year)][0] / eb[str(first)][0] if eb[str(first)][0] else None
    nat_e = {(r["device"], r["year"]): r for r in nat["by_device"]}[("E-bike", year)]
    emoto = {(r["type"], r["year"]): r for r in nat["by_ebike_type"]}.get(("likely e-moto", year))
    mix_txt, _ = age_mix_sentence(st, us_pop, groups, year)
    pts = [
        f"E-bike injuries are rising fast: about {fmt(eb[str(year)][0])} expected visits in {year}, "
        f"{up:.1f} times the {first} level (about {fmt(eb[str(first)][0])})." if up else "",
        mix_txt,
        f"Nationally, NEISS-AI estimates about {fmt(nat_e['est'])} US e-bike emergency visits in {year} "
        f"(likely range {fmt(nat_e['lo'])} to {fmt(nat_e['hi'])}). It reads each injury story to tell e-bikes "
        f"from mopeds, including before the 2024 change in official product codes."
        + (f" About {emoto['est'] / nat_e['est'] * 100:.1f}% of {year} e-bike visits look like e-motos "
           f"(electric motorcycles), a minimum." if emoto else ""),
    ]
    fcm = D.get("forecast")
    if fcm and st.get("fc"):
        f0, fN = fcm["years"][0], fcm["years"][-1]
        e1, eN, s1 = st["fc"]["E-bike"][str(f0)], st["fc"]["E-bike"][str(fN)], st["fc"]["E-scooter"][str(f0)]
        pts.append(f"Looking ahead: if national trends keep slowing as forecast, about {fmt(e1[0])} e-bike visits "
                   f"(80% range {fmt(e1[1])} to {fmt(e1[2])}) and {fmt(s1[0])} e-scooter visits are expected in {f0}, "
                   f"and about {fmt(eN[0])} e-bike visits in {fN}. National forecast tested on past years; assumes "
                   f"the state keeps its {fcm['base_year']} share.")
    y = bullets(c, M, y, [p for p in pts if p], W - 2 * M) - 4

    # charts
    cw = (W - 2 * M - 14) / 2
    c.setFont("Sans-Bold", 9)
    c.setFillColor(HexColor(INK))
    c.drawString(M, y, f"Expected visits, {years[0]}–{years[-1]}")
    c.drawString(M + cw + 14, y, f"Expected e-bike visits by age, {year}")
    y -= 4
    ch = 140
    c.drawImage(trend_chart(st, years, unstable), M, y - ch, width=cw, height=ch, preserveAspectRatio=True, anchor="nw")
    c.drawImage(age_chart(st, year, groups), M + cw + 14, y - ch, width=cw, height=ch, preserveAspectRatio=True,
                anchor="nw")
    y -= ch + 10
    notes = "Shaded bands and lines: ranges from the uncertainty in the national number only, not real differences between states."
    if any(unstable.get(("E-bike", yy)) for yy in years):
        un_years = [str(yy) for yy in years if unstable.get(("E-bike", yy))]
        notes += f" Open circles: the national e-bike estimate for {', '.join(un_years)} rests on few records (CPSC rule), so read it with care."
    y = para(c, M, y, notes, W - 2 * M, size=7.2, color=INK3) - 6

    # how calculated + limits (two columns)
    col_w = (W - 2 * M - 18) / 2
    yl = yr = y
    c.setFont("Sans-Bold", 9.5)
    c.setFillColor(HexColor(INK))
    c.drawString(M, yl, "How it is calculated")
    c.drawString(M + col_w + 18, yr, "Limits")
    yl = para(c, M, yl - 13, "1. NEISS-AI estimates national emergency department visits for each device and age group from "
              "the US Consumer Product Safety Commission's NEISS sample of about 100 hospitals, reading each "
              "short injury story.", col_w, size=7.6)
    yl = para(c, M, yl - 2, f"2. For each age group, the national number is multiplied by {the}'s share of the US "
              f"population in that age group (US Census Bureau), then the age groups are added up.",
              col_w, size=7.6)
    yl = para(c, M, yl - 2, "3. The range comes from the uncertainty in the national number, because NEISS samples about "
              "100 hospitals rather than all of them.", col_w, size=7.6)
    yl = para(c, M, yl - 2, "Note: e-scooter totals differ from CPSC's published figures.", col_w, size=7.6)
    yr = bullets(c, M + col_w + 18, yr - 13, [
        "NEISS does not record the patient's state, so these are expected numbers, not counts.",
        "They assume people in each age group get hurt at the national rate. Real numbers can be higher or lower "
        "where more people ride, roads differ, or laws differ.",
        "The ranges show only the uncertainty in the national number, not real differences between states.",
        "For planning and context; for counts, use state hospital or crash data, which NEISS-AI can complement.",
    ], col_w, size=7.6)
    y = min(yl, yr) - 6

    # citation box
    bh = 64
    c.setFillColor(HexColor(ACCENT_SOFT))
    c.setStrokeColor(HexColor(ACCENT_SOFT))
    c.roundRect(M, y - bh, W - 2 * M, bh, 6, stroke=0, fill=1)
    c.setFillColor(HexColor(INK))
    c.setFont("Sans-Bold", 8.6)
    c.drawString(M + 10, y - 14, "How to cite")
    cy = para(c, M + 10, y - 26, f"Kumar S. NEISS-AI: AI-assisted national injury estimates from NEISS emergency "
              f"department narratives [software]. Zenodo; 2026. {DOI}. State brief: {name}, {year}.",
              W - 2 * M - 20, size=7.6)
    para(c, M + 10, cy - 1, "Data: US Consumer Product Safety Commission, NEISS (national estimates); US Census "
         "Bureau, Vintage 2025 population estimates by age (SC-EST2025-ALLDATA6).", W - 2 * M - 20, size=7.2, color=INK2)
    y -= bh + 5

    # footer
    c.setFont("Sans", 7.4)
    c.setFillColor(HexColor(INK2))
    c.drawString(M, 40, f"Free custom analysis (for example a bill, report or campaign): {CONTACT}")
    c.drawString(M, 29, f"Explore and download: {SITE}#state?s={abbr}&y={year}")
    c.setFillColor(HexColor(INK3))
    c.drawRightString(W - M, 29, f"NEISS-AI {D.get('version') or ''} · data updated {D['updated']}")
    c.showPage()
    c.save()
    return path, y


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(DOCS / "data" / "state_estimates.json"))
    ap.add_argument("--national", default=str(DOCS / "data.json"))
    ap.add_argument("--out", default=str(DOCS / "briefs"))
    ap.add_argument("--year", type=int, default=None)
    ap.add_argument("--states", nargs="*")
    a = ap.parse_args()
    D = json.loads(Path(a.data).read_text(encoding="utf-8"))
    nat = json.loads(Path(a.national).read_text(encoding="utf-8"))
    year = a.year or max(D["years"])
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for abbr in a.states or list(D["states"]):
        p, y_left = build_one(D, nat, abbr, year, out)
        if y_left < 50:
            raise SystemExit(f"{abbr}: content runs into the footer (y={y_left:.0f})")
        print(f"{p.name}  ({os.path.getsize(p) // 1024} KB, space left above footer {y_left - 50:.0f}pt)")


if __name__ == "__main__":
    main()
