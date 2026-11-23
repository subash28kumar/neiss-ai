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
