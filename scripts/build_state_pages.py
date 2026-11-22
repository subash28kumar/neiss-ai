"""Build one plain, search-engine-friendly page per state, a states index, and sitemap.xml.

Why: the main site is one interactive page, so search engines mostly see its name. These
static pages let a search such as "e-bike injuries Massachusetts" find the right numbers.
Each page repeats, in plain English, what the "Your state" card shows, with the same rules:
injury numbers are estimates from national NEISS data and the state's population by age; road
deaths (NHTSA FARS) and biking to work (Census ACS) are real state data. Every page links to
the interactive view, the state brief and the "Compare your state" workbook, and carries
structured data (schema.org Dataset) describing what it is.

Run: python scripts/build_state_pages.py   (also run by update_site.py and the monthly refresh)
Writes docs/states/<state-name>.html, docs/states/index.html, docs/sitemap.xml
"""
from __future__ import annotations

import csv
import datetime as dt
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DATA = DOCS / "data"
MODEL = ROOT / "src" / "neissai" / "model"
SITE = "https://subash28kumar.github.io/neiss-ai/"
DOI = "https://doi.org/10.5281/zenodo.23306744"
DEVICES = ["E-bike", "E-scooter", "Bicycle"]


def r100(v: float) -> int:
    return int(round(v / 100.0)) * 100


def fmt(v: float) -> str:
    return f"{r100(v):,}" if v >= 1000 else f"{int(round(v / 10.0)) * 10:,}"


def one_in(pop: float, n: float) -> str:
    if not n:
        return "n/a"
    x = pop / n
    m = 10 ** (len(str(int(x))) - 2) if x >= 100 else 1
    return f"{int(round(x / m) * m):,}"


def money(v: float) -> str:
    if v >= 1e9:
        return f"${v / 1e9:.1f} billion"
    if v >= 1e7:
        return f"${round(v / 1e6):,} million"
    if v >= 1e6:
        return f"${v / 1e6:.1f} million"
    return f"${int(round(v / 1e4) * 1e4):,}"


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def load(name: str):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


CSS = """body{font:16px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:0;color:#1d1d1b;background:#fbfbfa}
main{max-width:860px;margin:0 auto;padding:28px 20px 60px}a{color:#1f5fbf}
.crumb{font-size:14px;color:#555}.lede{font-size:18px}
.k{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin:18px 0}
.k div{background:#f0efec;border-radius:10px;padding:12px 14px}.k b{display:block;font-size:22px}
.k span{font-size:13.5px;color:#444}table{border-collapse:collapse;width:100%;margin:10px 0 4px;font-size:15px}
th,td{text-align:right;padding:6px 8px;border-bottom:1px solid #e3e1dc}th:first-child,td:first-child{text-align:left}
.btn{display:inline-block;background:#1f5fbf;color:#fff;text-decoration:none;padding:10px 16px;border-radius:8px;margin:6px 8px 6px 0}
.btn.alt{background:#fff;color:#1f5fbf;border:1px solid #1f5fbf}.note{font-size:14px;color:#555}
h2{margin-top:30px;font-size:21px}ul{padding-left:20px}li{margin:6px 0}
@media (prefers-color-scheme:dark){body{background:#161616;color:#ececec}.k div{background:#232323}.k span,.note,.crumb{color:#b5b5b5}
th,td{border-color:#333}a{color:#7fb0ff}.btn{background:#3b7be0;color:#fff}.btn.alt{background:transparent;color:#7fb0ff;border-color:#7fb0ff}}"""


def page(ab: str, S: dict, deaths: dict | None, commute: dict | None, costs: dict | None, hosp: dict, year: int,
         names: dict, rank: dict, updated: str) -> str:
    st = S["states"][ab]
    N = st["name"]
    pop = sum(st["pop"][str(year)])
    e = {d: st["e"][d][str(year)] for d in DEVICES}
    eb = e["E-bike"]
    first = 2020 if "2020" in st["e"]["E-bike"] else min(int(y) for y in st["e"]["E-bike"])
    eb_first = st["e"]["E-bike"][str(first)][0]
    fc = (st.get("fc") or {}).get("E-bike") or {}
    fc_next = fc.get(str(year + 1))
    ages = st["age"]["E-bike"][str(year)]
    groups = S["age_groups"]
    top_age = groups[max(range(len(ages)), key=lambda i: ages[i][0])]
    stay = sum(ages[i][0] * hosp[g] for i, g in enumerate(groups))
    lines = []
    if deaths and ab in deaths["states"]:
        r, u = deaths["states"][ab], deaths["us"]
        cmp = "higher than" if r["rate_per_100k"] > u["rate_per_100k"] * 1.15 else "lower than" if r["rate_per_100k"] < u["rate_per_100k"] * 0.85 else "close to"
        lines.append(f"<li><b>Road deaths (real count):</b> in {deaths['year']}, {r['deaths']:,} "
                     f"{'bicyclist was' if r['deaths'] == 1 else 'bicyclists, including e-bike riders, were'} killed in traffic "
                     f"crashes with motor vehicles in {N}: {r['share_of_traffic_deaths_pct']}% of all traffic deaths, "
                     f"{r['rate_per_100k']} per 100,000 people, {cmp} the US rate of {u['rate_per_100k']}. "
                     f"<a href=\"{html.escape(deaths['url'])}\">Source: NHTSA FARS</a>.</li>")
    if commute and ab in commute["states"]:
        r, u = commute["states"][ab], commute["us"]
        lines.append(f"<li><b>Biking to work (real survey):</b> about {fmt(r['bicycle'])} people in {N} usually bike to work "
                     f"({r['share_pct']:.2f}% of workers; US {u['share_pct']:.2f}%), Census ACS {commute['year']}. "
                     f"More riding usually means more bike injuries.</li>")
    if costs:
        c = costs["cost_2025_usd"]
        py = costs.get("price_year", 2025)
        lines.append(f"<li><b>Medical bills (estimate):</b> e-bike injuries in {N} in {year} likely cost about "
                     f"{money(eb[0] * c['other_bicycle_injury'])} to {money(eb[0] * c['road_crash_with_motor_vehicle'])} in "
                     f"medical care ({py} dollars). The low number is if every injury cost like a fall with no car; the high "
                     f"number is if every injury cost like a crash with a car. <a href=\"{html.escape(costs['url'])}\">Source: CDC study</a>.</li>")
    rows = "".join(
        f"<tr><td>{y}</td>" + "".join(f"<td>{fmt(st['e'][d][str(y)][0])}</td>" for d in DEVICES) + "</tr>"
        for y in sorted(int(k) for k in st["e"]["E-bike"]))
    title = f"E-bike injuries in {N}: emergency department visits, {first}-{year} | NEISS-AI"
    desc = (f"About {fmt(eb[0])} e-bike emergency department visits in {N} in {year} (estimate, likely range {fmt(eb[1])} to "
            f"{fmt(eb[2])}), about 1 in {one_in(pop, eb[0])} residents. E-scooter and bicycle injuries, trend since {first}, "
            f"forecast, road deaths and medical costs. Free from NEISS-AI.")
    url = f"{SITE}states/{slug(N)}.html"
    ld = {"@context": "https://schema.org", "@type": "Dataset", "name": f"E-bike, e-scooter and bicycle injuries in {N} (NEISS-AI estimates)",
          "description": desc, "url": url, "isAccessibleForFree": True, "license": "https://creativecommons.org/licenses/by/4.0/",
          "creator": {"@type": "Person", "name": "Subash Kumar", "identifier": "https://orcid.org/0009-0003-6661-3424"},
          "spatialCoverage": {"@type": "Place", "name": f"{N}, United States"},
          "temporalCoverage": f"{first}/{year}", "dateModified": updated, "citation": DOI, "isBasedOn": "US CPSC National Electronic Injury Surveillance System (NEISS)",
          "keywords": ["e-bike injuries", f"e-bike injuries {N}", "e-scooter injuries", "bicycle injuries", "emergency department", "NEISS"],
          "distribution": [{"@type": "DataDownload", "encodingFormat": "application/pdf", "contentUrl": f"{SITE}briefs/NEISS-AI_State_Brief_{ab}_{year}.pdf"},
                           {"@type": "DataDownload", "encodingFormat": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            "contentUrl": f"{SITE}benchmarks/NEISS-AI_Compare_Your_State_{ab}_{year}.xlsx"}]}
    nxt = (f"<div><b>about {fmt(fc_next[0])}</b><span>expected in {year + 1} (80% range {fmt(fc_next[1])} to {fmt(fc_next[2])})</span></div>"
           if fc_next else "")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{html.escape(title)}"><meta property="og:description" content="{html.escape(desc)}">
<meta property="og:url" content="{url}"><meta property="og:image" content="{SITE}social.png"><meta property="og:type" content="article">
<script type="application/ld+json">{json.dumps(ld)}</script>
<style>{CSS}</style></head>
<body><main>
<p class="crumb"><a href="../">NEISS-AI</a> › <a href="./">States</a> › {html.escape(N)}</p>
<h1>E-bike injuries in {html.escape(N)}</h1>
<p class="lede">In {year}, about <b>{fmt(eb[0])}</b> people in {html.escape(N)} went to an emergency room after an e-bike injury
(likely range {fmt(eb[1])} to {fmt(eb[2])}). That is about {round(eb[0] / 365):,} a day, or 1 in {one_in(pop, eb[0])} residents,
and about {eb[0] / eb_first:.0f} times the {first} level.</p>
<p class="note">These injury numbers are estimates: national NEISS emergency department data, applied to {html.escape(N)}'s population
in each age group. NEISS does not record the patient's state, so no one can count them directly from it. The <b>likely range</b> means the true number is very likely (95%) inside it.</p>
<div class="k">
<div><b>about {fmt(eb[0])}</b><span>e-bike emergency department visits, {year}</span></div>
<div><b>1 in {one_in(pop, eb[0])}</b><span>residents had a visit</span></div>
<div><b>#{rank[ab]} of 51</b><span>states by number of e-bike visits</span></div>
{nxt}
</div>
<p><a class="btn" href="../#state?s={ab}">Open the interactive {html.escape(N)} view</a>
<a class="btn alt" href="../briefs/NEISS-AI_State_Brief_{ab}_{year}.pdf">One-page brief (PDF)</a>
<a class="btn alt" href="../benchmarks/NEISS-AI_Compare_Your_State_{ab}_{year}.xlsx">Compare with your own counts (Excel)</a></p>

<h2>E-bikes, e-scooters and bicycles, {first}-{year}</h2>
<table><tr><th>Year</th>{''.join(f'<th>{d}</th>' for d in DEVICES)}</tr>{rows}</table>
<p class="note">Estimated emergency department visits in {html.escape(N)}. In {year}: e-scooter about {fmt(e['E-scooter'][0])},
bicycle about {fmt(e['Bicycle'][0])}; about {e['E-bike'][0] / e['Bicycle'][0] * 10:.1f} e-bike injuries for every 10 bicycle injuries.</p>

<h2>Public health and transportation</h2>
<ul>
<li><b>Hospital stays:</b> about {fmt(stay)} of the {year} e-bike visits likely ended in a hospital stay (national hospital-stay
shares by age applied to {html.escape(N)}).</li>
<li><b>Who:</b> the most visits were among people aged {top_age}.</li>
{''.join(lines)}
</ul>

<h2>How to cite</h2>
<p>NEISS-AI (Kumar, 2026), state estimates from US CPSC NEISS emergency department data. <a href="{DOI}">{DOI}</a>.
Numbers updated {updated}.</p>
<p class="note">Other states: <a href="./">all 50 states and DC</a>. Free and open source: <a href="https://github.com/subash28kumar/neiss-ai">code</a>.</p>
</main></body></html>
"""


def main() -> None:
    S = load("state_estimates.json")
    D = json.loads((DOCS / "data.json").read_text(encoding="utf-8"))
    deaths, commute, costs = load("state_cyclist_deaths.json"), load("state_bike_commute.json"), load("injury_medical_costs.json")
    year = max(int(y) for y in S["states"]["CA"]["e"]["E-bike"])
    share = {r["age_group"]: r["share"] for r in D["hospitalized"] if r["device"] == "E-bike"}
    hosp = {}
    for g in S["age_groups"]:
        hosp[g] = share["0-17"] if g in ("Under 5", "5-13", "14-17") else share["65+"] if g == "65+" else share["18-64"]
    order = sorted(S["states"], key=lambda a: -S["states"][a]["e"]["E-bike"][str(year)][0])
    rank = {a: i + 1 for i, a in enumerate(order)}
    names = {a: S["states"][a]["name"] for a in S["states"]}
    updated = str(D.get("updated") or dt.date.today().isoformat())[:10]
    out = DOCS / "states"
    out.mkdir(exist_ok=True)
    for f in out.glob("*.html"):
        f.unlink()
    for ab in sorted(S["states"], key=lambda a: names[a]):
        (out / f"{slug(names[ab])}.html").write_text(page(ab, S, deaths, commute, costs, hosp, year, names, rank, updated), encoding="utf-8")
    items = "".join(f"<li><a href=\"{slug(names[a])}.html\">{html.escape(names[a])}</a>: about {fmt(S['states'][a]['e']['E-bike'][str(year)][0])} e-bike emergency department visits in {year}</li>"
                     for a in sorted(S["states"], key=lambda a: names[a]))
    idx_desc = f"E-bike, e-scooter and bicycle injury estimates for all 50 states and DC, {year}: emergency department visits, trends, forecasts, road deaths and medical costs. Free from NEISS-AI."
    (out / "index.html").write_text(f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>E-bike injuries by state, {year} | NEISS-AI</title><meta name="description" content="{html.escape(idx_desc)}">
<link rel="canonical" href="{SITE}states/"><style>{CSS}</style></head><body><main>
<p class="crumb"><a href="../">NEISS-AI</a> › States</p><h1>E-bike injuries by state, {year}</h1>
<p class="lede">Pick a state for its e-bike, e-scooter and bicycle injury numbers, trend, forecast, road deaths and medical costs.
Injury numbers are estimates from national NEISS emergency department data and each state's population by age.</p>
<ul>{items}</ul><p><a class="btn" href="../#state">Open the interactive map</a></p></main></body></html>
""", encoding="utf-8")
    urls = [SITE, f"{SITE}states/", f"{SITE}press.html"] + [f"{SITE}states/{slug(names[a])}.html" for a in sorted(S["states"], key=lambda a: names[a])]
    sm = "".join(f"<url><loc>{u}</loc><lastmod>{updated}</lastmod></url>\n" for u in urls)
    (DOCS / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{sm}</urlset>\n', encoding="utf-8")
    print(f"wrote {len(S['states'])} state pages, states/index.html and sitemap.xml ({len(urls)} URLs)")


if __name__ == "__main__":
    main()
