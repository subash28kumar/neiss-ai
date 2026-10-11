"""Rebuild docs/index.html from docs/template.html and docs/data.json (data is inlined so the page works anywhere)."""
from pathlib import Path
root = Path(__file__).resolve().parents[1] / "docs"
html = (root / "template.html").read_text().replace("/*DATA*/null", (root / "data.json").read_text())
(root / "index.html").write_text(html)
print("wrote", root / "index.html")
