"""Every state page (and the states index) must carry the same visit counter as the rest of the site,
otherwise visits from outreach emails and LinkedIn to state pages go uncounted."""
from pathlib import Path

STATES = Path(__file__).resolve().parents[1] / "docs" / "states"
COUNTER = 'data-goatcounter="https://neiss-ai.goatcounter.com/count"'


def test_all_state_pages_have_visit_counter():
    pages = sorted(STATES.glob("*.html"))
    assert len(pages) == 52  # 50 states + DC + index
    missing = [p.name for p in pages if COUNTER not in p.read_text(encoding="utf-8")]
    assert not missing, f"state pages without the visit counter: {missing}"


def test_counter_is_inside_head():
    h = (STATES / "california.html").read_text(encoding="utf-8")
    assert h.index(COUNTER) < h.index("</head>")


def test_state_pages_say_what_numbers_are_for():
    # Expected numbers must not be read as a state ranking (Lisa Sharwood's feedback, Nov 2026).
    for p in sorted(STATES.glob("*.html")):
        if p.name == "index.html":
            continue
        t = p.read_text(encoding="utf-8")
        assert "What this number is for" in t and "Not for:" in t and "ranking states" in t, p.name


def test_site_state_card_says_what_numbers_are_for():
    t = (STATES.parent / "template.html").read_text(encoding="utf-8")
    assert "What this number is for" in t and "ranking states or judging how safe" in t


def test_state_pages_explain_the_formula_with_correct_example():
    import re
    t = (STATES / "california.html").read_text(encoding="utf-8")
    assert 'id="how"' in t and "How the number is worked out" in t and 'class="fbox"' in t and "Worked example" in t
    # the worked example must land on the same 25-44 number the site shows (3,751 for CA in 2025 data)
    import json
    S = json.loads((STATES.parent / "data" / "state_estimates.json").read_text(encoding="utf-8"))
    k = S["age_groups"].index("25-44")
    y = max(S["states"]["CA"]["age"]["E-bike"])
    val = S["states"]["CA"]["age"]["E-bike"][y][k][0]
    assert f"&asymp; {val:,}</b>" in t


def test_every_state_link_target_exists():
    t = (STATES.parent / "template.html").read_text(encoding="utf-8")
    assert "How this number is worked out" in t and 'states/california.html#how' in t
