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
    pub = json.loads(m.group(1).replace("'", '"').replace("2021:", '"2021":').replace("2022:", '"2022":')
                     .replace("2023:", '"2023":').replace("2024:", '"2024":'))
    # CPSC April 2026 report, Appendix B
    assert pub["E-bike"] == {"2022": 26800, "2023": 37600, "2024": 59200}
    assert pub["E-scooter"] == {"2021": 61200, "2022": 74800, "2023": 58400, "2024": 79300}


def test_ebike_claim_within_5_percent_still_true():
    d = json.loads((DOCS / "data.json").read_text())
    rows = {(r["year"], r["device"]): r["est"] for r in d["by_device"]}
    for y, c in {2022: 26800, 2023: 37600, 2024: 59200}.items():
        assert abs(rows[(y, "E-bike")] / c - 1) < 0.05


def test_escooter_mismatch_is_disclosed():
    html, press = _html(), _html("press.html")
    assert "E-scooter totals: NEISS-AI and CPSC do not match" in html
    assert "do not match CPSC" in press and "79,300" in press


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
