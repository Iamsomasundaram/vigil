"""The learning site must build, and every internal link and code include must resolve."""

import re
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"


def test_site_builds_with_no_broken_links():
    sys.path.insert(0, str(DOCS))
    import build_site

    build_site.build()  # raises SystemExit if an {{include}} symbol no longer exists in the code

    broken = []
    for page in DOCS.rglob("*.html"):
        text = page.read_text(encoding="utf-8")
        for href in re.findall(r'(?:href|src)="([^"#:]+?)(?:#[^"]*)?"', text):
            if not (page.parent / href).resolve().exists():
                broken.append(f"{page.relative_to(DOCS)} -> {href}")
    assert not broken, broken
