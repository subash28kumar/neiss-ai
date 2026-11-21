"""Keep the outside data on the "Your state" card up to date, automatically and safely.

Run every month by .github/workflows/refresh-context.yml. Each source is fetched from the
official raw data (not from PDF reports), checked, and only written if every check passes.
If a check fails, nothing is written for that source and the problem is reported, so the
website never shows half-updated or broken numbers.

Sources
  acs         US Census Bureau, American Community Survey 1-year, Table B08301 (biking to work),
              from the official ACS table-based summary file (no key needed)          -> docs/data/state_bike_commute.json
  fars        NHTSA Fatality Analysis Reporting System (FARS) national CSV files: bicyclists and
              other cyclists killed, by state            -> docs/data/state_cyclist_deaths.json
  cpi         US Bureau of Labor Statistics, CPI-U Medical care (CUUS0000SAM, semiannual), from
              the official BLS API; updates the prices in -> docs/data/injury_medical_costs.json
  population  US Census Bureau state population estimates (newest vintage): totals and by age
                                                         -> src/neissai/model/state_population*.csv

Usage
  python scripts/refresh_context.py all [--dry-run] [--report report.md]
  python scripts/refresh_context.py fars --check-year 2024   (compare with a known year)

Exit code 0 = finished (some sources may be unchanged); 1 = at least one source failed a check.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import math
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"
MODEL = ROOT / "src" / "neissai" / "model"
UA = {"User-Agent": "NEISS-AI data refresh (https://github.com/subash28kumar/neiss-ai)"}

FIPS = {"01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE",
        "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA",
        "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN",
        "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH", "34": "NJ", "35": "NM",
        "36": "NY", "37": "NC", "38": "ND", "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
        "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA",
        "54": "WV", "55": "WI", "56": "WY"}


class CheckFailed(Exception):
    pass


class Unreachable(Exception):
    """The source did not answer (outage). Not a data problem: try again next month."""


def get(url: str, timeout: int = 120, data: bytes | None = None, headers: dict | None = None) -> bytes | None:
    """Download a URL. Returns None if it does not exist (404/400); raises on other errors."""
    import time
    last = None
    for attempt in range(3):
        req = urllib.request.Request(url, data=data, headers={**UA, **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (400, 403, 404, 204):
                return None
            last = e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
        time.sleep(15 * (attempt + 1))
    raise Unreachable(f"{url.split('/')[2]} did not answer ({last})")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def write_if_changed(path: Path, doc, dry: bool) -> bool:
    new = json.dumps(doc, indent=1) + "\n"
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old is not None and json.loads(old) == doc:
        return False
    if not dry:
        path.write_text(new, encoding="utf-8")
    return True


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise CheckFailed(msg)


# ---------------------------------------------------------------- ACS: biking to work
def acs(dry: bool, check_year: int | None = None) -> str:
    path = DATA / "state_bike_commute.json"
    cur = load(path)
    have = cur["year"] if cur else 0
    this_year = dt.date.today().year
    for year in ([check_year] if check_year else range(this_year, have, -1)):
        # Official ACS table-based summary file (no key needed): one pipe-separated file per table.
        url = (f"https://www2.census.gov/programs-surveys/acs/summary_file/{year}/table-based-SF/data/"
               f"1YRData/acsdt1y{year}-b08301.dat")
        raw = get(url, timeout=300)
        if not raw:
            if check_year:
                return f"{year}: no summary file yet at {url}"
            continue
        rd = csv.DictReader(io.StringIO(raw.decode("utf-8", "replace")), delimiter="|")
        cols = {k.upper(): k for k in (rd.fieldnames or [])}
        need = ["GEO_ID", "B08301_E001", "B08301_M001", "B08301_E018", "B08301_M018"]
        check(all(n in cols for n in need), f"ACS {year}: unexpected columns {list(cols)[:8]}")
        out, T, B = {}, 0, 0
        for r in rd:
            g = r[cols["GEO_ID"]]
            if not g.startswith("0400000US"):
                continue
            ab = FIPS.get(g[-2:])
            if not ab:
                continue  # Puerto Rico
            y, my, x, mx = (int(float(r[cols[k]])) for k in need[1:])
            check(y > 0 and 0 <= x < y, f"ACS {year} {ab}: impossible numbers (workers {y}, bicycle {x})")
            p = x / y
            inner = mx ** 2 - (p ** 2) * (my ** 2)
            mp = math.sqrt(inner if inner > 0 else mx ** 2 + (p ** 2) * (my ** 2)) / y
            out[ab] = {"workers": y, "bicycle": x, "bicycle_moe90": abs(mx), "share_pct": round(100 * p, 2),
                       "share_moe90_pct": round(100 * mp, 2)}
            T += y
            B += x
        check(len(out) == 51, f"ACS {year}: expected 51 states and DC, got {len(out)}")
        share = 100 * B / T
        check(0.2 < share < 1.5, f"ACS {year}: US bike-to-work share {share:.2f}% is outside 0.2-1.5%")
        if cur:
            check(0.6 < T / cur["us"]["workers"] < 1.4, f"ACS {year}: total workers changed too much")
        doc = {"source": f"US Census Bureau, American Community Survey {year} 1-year estimates, Table B08301 "
                         f"(Means of Transportation to Work), from the official ACS summary file",
               "url": f"https://data.census.gov/table/ACSDT1Y{year}.B08301", "year": year,
               "note": (cur or {}).get("note", "Workers 16 years and over whose usual way to get to work was a bicycle."),
               "us": {"workers": T, "bicycle": B, "share_pct": round(share, 2)},
               "states": dict(sorted(out.items()))}
        if check_year:
            same = cur and cur["year"] == year and cur["states"] == doc["states"]
            nd = sum(1 for k in out if not cur or cur["states"].get(k) != out[k])
            return f"{year}: US {doc['us']}; CA {out['CA']}; matches the file on the site: {bool(same)} (states different: {nd})"
        return f"updated to {year}" if write_if_changed(path, doc, dry) else f"{year} already in use"
    return f"no newer year than {have}"


# ---------------------------------------------------------------- FARS: cyclist deaths
def fars_year(year: int) -> dict | None:
    raw = get(f"https://static.nhtsa.gov/nhtsa/downloads/FARS/{year}/National/FARS{year}NationalCSV.zip", timeout=600)
    if not raw:
        return None
    z = zipfile.ZipFile(io.BytesIO(raw))
    name = next((n for n in z.namelist() if n.lower().endswith("person.csv")), None)
    check(name is not None, f"FARS {year}: no person.csv in the zip")
    cyc, allk = {}, {}
    with z.open(name) as f:
        rd = csv.DictReader(io.TextIOWrapper(f, encoding="latin-1"))
        for r in rd:
            if r.get("INJ_SEV") != "4":  # 4 = fatal injury
                continue
            ab = FIPS.get(r["STATE"].zfill(2))
            if not ab:
                continue
            allk[ab] = allk.get(ab, 0) + 1
            if r.get("PER_TYP") in ("6", "7"):  # 6 = bicyclist, 7 = other cyclist
                cyc[ab] = cyc.get(ab, 0) + 1
    return {"cyc": cyc, "all": allk, "file": name}


def fars(dry: bool, check_year: int | None = None) -> str:
    path = DATA / "state_cyclist_deaths.json"
    cur = load(path)
    have = cur["year"] if cur else 0
    pops = {}
    for r in csv.DictReader((MODEL / "state_population.csv").open(encoding="utf-8")):
        pops[(r["abbr"], int(r["year"]))] = int(r["population"])
    years = [check_year] if check_year else range(dt.date.today().year - 1, have, -1)
    for year in years:
        got = fars_year(year)
        if not got:
            continue
        cyc, allk = got["cyc"], got["all"]
        check(len(allk) == 51, f"FARS {year}: deaths found for {len(allk)} states, expected 51")
        tot_c, tot_a = sum(cyc.values()), sum(allk.values())
        check(700 < tot_c < 2000 and 25000 < tot_a < 60000, f"FARS {year}: totals look wrong ({tot_c} cyclists, {tot_a} all)")
        if cur and not check_year:
            check(0.7 < tot_c / cur["us"]["deaths"] < 1.4, f"FARS {year}: cyclist deaths changed too much vs {have}")
        py = year if ("CA", year) in pops else max(y for (_, y) in pops)
        out = {}
        for ab in sorted(allk):
            d, a, p = cyc.get(ab, 0), allk[ab], pops[(ab, py)]
            out[ab] = {"deaths": d, "share_of_traffic_deaths_pct": round(100 * d / a, 1),
                       "rate_per_100k": round(d / p * 1e5, 2), "traffic_deaths": a}
        usp = sum(pops[(ab, py)] for ab in out)
        doc = {"source": f"NHTSA, Fatality Analysis Reporting System (FARS) {year}, national CSV files "
                         f"(person file: bicyclists and other cyclists, fatal injury); population: US Census Bureau ({py})",
               "url": "https://www.nhtsa.gov/research-data/fatality-analysis-reporting-system-fars", "year": year,
               "note": "Bicyclists and other cyclists killed in traffic crashes involving a motor vehicle in transport on a "
                       "public road. Since 2022 includes riders of bicycles powered by pedals, motors, or both (so e-bike riders "
                       "are included). Real counts, not estimates. NHTSA updates a year's file once (preliminary, then final), "
                       "so numbers can change slightly.",
               "us": {"deaths": tot_c, "share_of_traffic_deaths_pct": round(100 * tot_c / tot_a, 1),
                      "rate_per_100k": round(tot_c / usp * 1e5, 2), "traffic_deaths": tot_a},
               "states": out}
        if check_year:
            return json.dumps({"year": year, "us": doc["us"], "CA": out["CA"], "FL": out["FL"], "MA": out["MA"], "WY": out["WY"]})
        changed = write_if_changed(path, doc, dry)
        if changed and have == year:
            return f"{year} revised by NHTSA (newer file)"
        return f"updated to {year}" if changed else f"{year} already in use"
    return f"no newer year than {have}"


# ---------------------------------------------------------------- CPI: medical prices
def cpi(dry: bool) -> str:
    path = DATA / "injury_medical_costs.json"
    cur = load(path)
    check(cur is not None, "costs file missing")
    this = dt.date.today().year
    halves, via = {}, "BLS API"
    try:
        body = json.dumps({"seriesid": ["CUUS0000SAM"], "startyear": str(this - 3), "endyear": str(this)}).encode()
        raw = get("https://api.bls.gov/publicAPI/v1/timeseries/data/", data=body, headers={"Content-Type": "application/json"})
        js = json.loads(raw or b"{}")
        check(js.get("status") == "REQUEST_SUCCEEDED", f"BLS API: {js.get('status')} {js.get('message')}")
        for p in js["Results"]["series"][0]["data"]:
            if p["period"] in ("S01", "S02") and p["value"] not in ("-", ""):
                halves.setdefault(int(p["year"]), {})[p["period"]] = float(p["value"])
    except (Unreachable, CheckFailed):
        # Same official BLS series, as republished by the Federal Reserve Bank of St. Louis (FRED).
        via = "FRED copy of the BLS series"
        raw = get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=CUUS0000SAM")
        check(raw is not None, "FRED did not return the series")
        for r in csv.DictReader(io.StringIO(raw.decode("utf-8"))):
            d, val = r.get("observation_date") or r.get("DATE"), r.get("CUUS0000SAM")
            if not d or val in (None, "", "."):
                continue
            y, m = int(d[:4]), int(d[5:7])
            halves.setdefault(y, {})["S01" if m == 1 else "S02"] = float(val)
    full = [y for y, v in halves.items() if len(v) == 2]
    check(bool(full), "BLS API: no year with both halves")
    year = max(full)
    have = int(cur.get("price_year", 2025))
    if year <= have:
        known = cur["price_update"].get("index_2025_avg") if have == 2025 else cur["price_update"].get("index_latest_avg")
        got = round((halves[have]["S01"] + halves[have]["S02"]) / 2, 3) if len(halves.get(have, {})) == 2 else None
        return f"{have} prices already in use (via {via}; index {got} vs file {known})"
    idx = (halves[year]["S01"] + halves[year]["S02"]) / 2
    base = cur["price_update"]["index_2015_avg"]
    f = idx / base
    check(1.0 < f < 2.5, f"price factor {f:.3f} looks wrong")
    new = dict(cur)
    new["price_year"] = year
    new["price_update"] = {**cur["price_update"], "index_latest_year": year, "index_latest_avg": round(idx, 3), "factor": round(f, 4)}
    new["price_update"].pop("index_2025_avg", None)
    new["cost_latest_usd"] = {k: round(v * f) for k, v in cur["cost_2015_usd"].items()}
    new["cost_2025_usd"] = new["cost_latest_usd"]  # field kept for the website; holds the latest prices
    return f"updated to {year} prices" if write_if_changed(path, new, dry) else "unchanged"


# ---------------------------------------------------------------- Census population estimates
def population(dry: bool, check_vintage: int | None = None) -> str:
    rows = list(csv.DictReader((MODEL / "state_population.csv").open(encoding="utf-8")))
    have = max(int(r["source"].split("Vintage ")[1][:4]) for r in rows)
    this = dt.date.today().year
    for v in ([check_vintage] if check_vintage else range(this, have, -1)):
        base = f"https://www2.census.gov/programs-surveys/popest/datasets/2020-{v}/state"
        tot = get(f"{base}/totals/NST-EST{v}-ALLDATA.csv", timeout=300)
        age = get(f"{base}/asrh/sc-est{v}-alldata6.csv", timeout=600)
        if not tot or not age:
            continue  # totals come out in December, age detail in June: wait for both
        years = range(2020, v + 1)
        abbr_of = {r["state"]: r["abbr"] for r in rows}
        totals = {}
        for r in csv.DictReader(io.StringIO(tot.decode("latin-1"))):
            if r.get("SUMLEV") == "040" and r["NAME"] in abbr_of:
                for y in years:
                    totals[(abbr_of[r["NAME"]], y)] = int(r[f"POPESTIMATE{y}"])
        check(len({a for a, _ in totals}) == 51, f"Vintage {v}: totals for {len({a for a, _ in totals})} states")
        sys.path.insert(0, str(ROOT / "src"))
        from neissai.state import AGE_GROUPS, age_group
        pop = {}
        for r in csv.DictReader(io.StringIO(age.decode("latin-1"))):
            if r["SEX"] != "0" or r["ORIGIN"] != "0" or r["RACE"] not in {"1", "2", "3", "4", "5", "6"} or r["NAME"] not in abbr_of:
                continue
            g = age_group(int(r["AGE"]))
            for y in years:
                pop.setdefault((abbr_of[r["NAME"]], y), [0] * len(AGE_GROUPS))[g] += int(r[f"POPESTIMATE{y}"])
        for k, groups in pop.items():
            check(sum(groups) == totals[k], f"Vintage {v} {k}: age groups {sum(groups):,} != total {totals[k]:,}")
            check(min(groups) > 0, f"Vintage {v} {k}: empty age group")
        check(len(pop) == 51 * len(years), f"Vintage {v}: {len(pop)} state-years, expected {51 * len(years)}")
        name_of = {a: s for s, a in abbr_of.items()}
        if check_vintage:
            cur_t = {(r["abbr"], int(r["year"])): int(r["population"]) for r in rows}
            cur_a = {}
            for r in csv.DictReader((MODEL / "state_population_age.csv").open(encoding="utf-8")):
                cur_a.setdefault((r["abbr"], int(r["year"])), {})[r["age_group"]] = int(r["population"])
            diff_t = sum(1 for k in totals if cur_t.get(k) != totals[k])
            diff_a = sum(1 for k in pop for (_, _, lab), val in zip(AGE_GROUPS, pop[k]) if cur_a.get(k, {}).get(lab) != val)
            return f"Vintage {v}: rebuilt from Census files; differences from the site's files: totals {diff_t}, age cells {diff_a}"
        src_t = f"US Census Bureau, Vintage {v} estimates NST-EST{v}-POP (July 1)"
        src_a = f"US Census Bureau, Vintage {v} estimates SC-EST{v}-ALLDATA6 (July 1 resident population)"
        if not dry:
            with (MODEL / "state_population.csv").open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["state", "abbr", "year", "population", "source"])
                for (a, y) in sorted(totals, key=lambda k: (name_of[k[0]], k[1])):
                    w.writerow([name_of[a], a, y, totals[(a, y)], src_t])
            with (MODEL / "state_population_age.csv").open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["state", "abbr", "year", "age_group", "population", "source"])
                for (a, y) in sorted(pop, key=lambda k: (name_of[k[0]], k[1])):
                    for (_, _, label), val in zip(AGE_GROUPS, pop[(a, y)]):
                        w.writerow([name_of[a], a, y, label, val, src_a])
        return f"updated to Vintage {v} (years 2020-{v})"
    return f"no newer vintage than {have}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["acs", "fars", "cpi", "population", "all"])
    ap.add_argument("--dry-run", action="store_true", help="fetch and check, but write nothing")
    ap.add_argument("--check-year", type=int, help="acs/fars: compute one year and print it (no writing)")
    ap.add_argument("--check-vintage", type=int, help="population: rebuild one vintage and compare (no writing)")
    ap.add_argument("--report", help="write a short Markdown report here")
    a = ap.parse_args()
    jobs = {"acs": acs, "fars": fars, "cpi": cpi, "population": population}
    todo = list(jobs) if a.what == "all" else [a.what]
    lines, failed = [], False
    for name in todo:
        try:
            if name == "fars" and a.check_year:
                msg = fars(True, a.check_year)
            elif name == "acs" and a.check_year:
                msg = acs(True, a.check_year)
            elif name == "population" and a.check_vintage:
                msg = population(True, a.check_vintage)
            else:
                msg = jobs[name](a.dry_run)
            lines.append(f"- {name}: {msg}")
        except Unreachable as e:
            lines.append(f"- {name}: could not reach the source this month, nothing changed; will try again next month ({e})")
        except Exception as e:  # noqa: BLE001 - report every failure, keep going with the rest
            failed = True
            lines.append(f"- {name}: FAILED, nothing written ({type(e).__name__}: {e})")
    report = "\n".join(lines)
    print(report)
    if a.report:
        Path(a.report).write_text(report + "\n", encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
