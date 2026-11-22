"""Guards for the Nov 2026 audit: public claims must match the data and stay honest."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parents[1] / "docs"


def _html(name="index.html"):
    return (DOCS / name).read_text()


def test_cpsc_tables_are_computed_from_data_not_typed():
    html = _html()
    assert 'id="cpscEbike"' in html and 'id="cpscEsc"' in html
    # no stale hand-typed comparison numbers
    assert "+4.4% (2022)" not in html and "<td>37,900</td>" not in html
    m = re.search(r"const CPSC_PUB=(\{.*?\});", html)
    pub = json.loads(m.group(1).replace("'", '"').replace("2019:", '"2019":').replace("2021:", '"2021":').replace("2022:", '"2022":')
                     .replace("2023:", '"2023":').replace("2024:", '"2024":'))
    # CPSC April 2026 report, Appendix B
    assert pub["E-bike"] == {"2022": 26800, "2023": 37600, "2024": 59200}
    assert pub["E-scooter"] == {"2019": 39100, "2021": 61200, "2022": 74800, "2023": 58400, "2024": 79300}


def test_ebike_claim_within_5_percent_still_true():
    d = json.loads((DOCS / "data.json").read_text())
    rows = {(r["year"], r["device"]): r["est"] for r in d["by_device"]}
    for y, c in {2022: 26800, 2023: 37600, 2024: 59200}.items():
        assert abs(rows[(y, "E-bike")] / c - 1) < 0.05


def test_escooter_mismatch_is_disclosed():
    html, press = _html(), _html("press.html")
    assert "E-scooter totals: NEISS-AI and CPSC do not match" in html
    assert "do not match CPSC" in press and "79,300" in press
    # Independent review (Nov 2026): no trend claim for e-scooters; classifier limits stated
    assert "still useful for trends" not in html and "not reliable for trends" in html
    assert "every year is counted the same way" not in html
    assert "not yet tested" in html and "validated text classifier" not in press


def test_search_and_children_wording_are_not_overstated():
    html = _html()
    assert "Search the stories of the bike and scooter injuries on this site" in html
    assert "e-bike injuries are more serious than bicycle injuries" not in html


def test_press_page_reply_promise_matches_site():
    press = _html("press.html")
    assert "within one day" not in press and "1–2 working days" in press
    assert "Updated October 2026" not in press


@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="pdftotext not installed")
def test_fact_sheet_matches_data_and_uses_main_doi():
    pdf = DOCS / "NEISS-AI_FactSheet1_Ebike_Injuries_US_2019-2025.pdf"
    text = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True).stdout
    d = json.loads((DOCS / "data.json").read_text())
    est = [r["est"] for r in d["by_device"] if r["device"] == "E-bike" and r["year"] == max(x["year"] for x in d["by_device"])][0]
    assert f"{round(est / 100) * 100:,}" in text
    assert "10.5281/zenodo.23306744" in text and "23550272" not in text


def test_escooter_note_on_state_pages_card_and_downloads():
    import html as _h
    import zipfile
    assert "differ from CPSC's published e-scooter figures" in _html("states/massachusetts.html")
    assert "treat state e-scooter numbers with care" in _html()
    # read the workbook's text directly (an .xlsx is a zip of XML), so no spreadsheet library is needed
    with zipfile.ZipFile(DOCS / "NEISS-AI_DataPack.xlsx") as z:
        text = " ".join(_h.unescape(z.read(n).decode("utf-8")) for n in z.namelist() if n.endswith(".xml"))
    assert "differ from CPSC's published e-scooter figures" in text


@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="pdftotext not installed")
def test_state_brief_has_escooter_note():
    text = subprocess.run(["pdftotext", str(DOCS / "briefs" / "NEISS-AI_State_Brief_MA_2025.pdf"), "-"],
                          capture_output=True, text=True).stdout
    assert "e-scooter totals differ from CPSC" in text


def test_every_state_page_matches_state_data_with_site_rounding():
    import html as _h
    import math
    s = json.loads((DOCS / "data" / "state_estimates.json").read_text())
    y = str(s["years"][-1])

    def fmt(v):
        v = float(v)
        if v >= 1000:
            return f"{math.floor(v / 100 + 0.5) * 100:,}"
        if v >= 100:
            return f"{math.floor(v / 10 + 0.5) * 10:,}"
        return f"{math.floor(v + 0.5):,}"

    for ab, st in s["states"].items():
        slug = st["name"].lower().replace(" ", "-").replace(".", "")
        t = re.sub(r"\s+", " ", _h.unescape(re.sub(r"<[^>]+>", " ", (DOCS / "states" / f"{slug}.html").read_text())))
        eb = st["e"]["E-bike"][y]
        for v in eb[:3]:
            assert fmt(v) in t, (ab, v)


def test_ask_reads_ages_sex_and_missing_years_honestly():
    html = _html()
    # "women"/"men"/"adults" no longer silently means 18-64 only
    assert "'18+':[18,999]" in html and "\\bwomen\\b/.test(t)) f.age='18+'" in html
    # a year with no data gets a plain message, not another period's total
    assert "No data for that year yet." in html
    # several search words are described as words, not as an exact phrase
    assert "contain all of the words" in html


def test_hospital_stay_definition_is_the_same_everywhere():
    import inspect
    from neissai import devices
    assert '"2", "4", "5", "8"' in inspect.getsource(devices.add_outcomes)
    src = (Path(__file__).resolve().parents[1] / "scripts" / "build_fact_sheet.py").read_text()
    assert "isin([2, 4, 5, 8])" in src
    assert "rare deaths" in _html()


def test_state_outputs_do_not_claim_state_level_certainty_or_rank():
    # Independent review (Nov 22, 2026): state numbers are the national rate applied to the state's
    # population, so a 95% "true number" claim and a state ranking overstate them.
    for f in (DOCS / "states").glob("*.html"):
        t = f.read_text()
        assert "very likely (95%)" not in t, f.name
        assert " of 51</b>" not in t, f.name
    md = _html("states/maryland.html")
    assert "These are expected numbers, not counts." in md
    assert "not how" in md and "differs from other states" in md
    html = _html()
    assert "#${C.rank} of ${C.n}" not in html
    assert "residents had a visit" not in html
    src = (DOCS.parent / "scripts" / "build_state_briefs.py").read_text()
    assert "very likely, 95%" not in src


def test_visitor_wording_after_independent_review():
    html = _html()
    assert "Answer key: AI reviewers" in html                     # story tests say who made the key
    assert "233 of 240 raw = 97.1%" in html                        # weighted vs raw e-moto score
    assert "Look-back test" in html and "list to review, not an alarm" in html
    assert "nearly touch" not in html and "overlap a little" in html
    assert "bicycle product code 5040 alone" in html
    assert "also includes electric skateboards, one-wheels and Segways" in html
    emb = _html("embed.html")
    assert "zenodo.23550272" not in emb and "zenodo.23306744" in emb
    assert "not reliable for trends" in emb


def test_fact_sheet_uses_site_definition_for_head_and_fracture():
    src = (DOCS.parent / "scripts" / "build_fact_sheet.py").read_text()
    assert 'df["Body_Part_2"].isin' in src and 'df["Diagnosis_2"] == 57' in src


def test_own_notes_reads_kmh():
    from neissai.freetext import label_note
    assert label_note("fell off e-bike riding at 40 km/h")["rider_mph"] == 25
