"""Site wording added after expert feedback (Nov 2026)."""
from pathlib import Path

T = (Path(__file__).resolve().parents[1] / "docs" / "template.html").read_text(encoding="utf-8")


def test_search_tab_says_where_stories_come_from():
    assert "CPSC publishes these stories every year in its public" in T
    assert "<i>delivery</i>)" not in T  # stray bracket fixed


def test_no_llm_answer_is_on_how_it_works():
    assert "Does NEISS-AI use a large language model" in T
    assert "the same story always gets the same answer" in T
