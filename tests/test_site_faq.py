"""Site wording added after expert feedback (Nov 2026)."""
from pathlib import Path

T = (Path(__file__).resolve().parents[1] / "docs" / "template.html").read_text(encoding="utf-8")


def test_search_tab_says_where_stories_come_from():
    assert "CPSC publishes these stories every year in its public" in T
    assert "<i>delivery</i>)" not in T  # stray bracket fixed


def test_no_llm_answer_is_on_how_it_works():
    assert "Does NEISS-AI use a large language model" in T
    assert "the same story always gets the same answer" in T


def test_no_consistent_counts_claim_anywhere():
    root = Path(__file__).resolve().parents[1]
    for f in ["docs/template.html", "docs/press.html", "scripts/build_data_pack.py", "README.md"]:
        assert "stay consistent across" not in (root / f).read_text(encoding="utf-8"), f


def test_your_state_tab_has_highlighted_formula_box():
    assert 'id="stformula"' in T and "national visits</span> &divide;" in T


def test_how_each_device_is_identified_table():
    assert 'id="devicerules"' in T and "Code 5022 (powered scooters, from 2020)" in T
    # rules described must match the code
    import re
    src = (Path(__file__).resolve().parents[1] / "src" / "neissai" / "devices.py").read_text(encoding="utf-8")
    for code in ["5045", "3215", "5022", "5040", "5033", "5023", "5024", "1329", "5025", "5042", "1333", "5046", "5035"]:
        assert code in src and code in T, code
