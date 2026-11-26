"""
The learning UI must stay complete and consistent: every sidebar entry has a page, every page has a
place in the sidebar and a guide link that points at a real guide page, every level, architecture and
reliability page in the guide is reachable, and every page renders without raising.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / "ui"
GUIDE_SRC = ROOT / "docs" / "src"


def _load_nav():
    """ui/nav.py is pure data, so it can be loaded without Streamlit or the other UI modules."""
    spec = importlib.util.spec_from_file_location("vigil_ui_nav", UI / "nav.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


NAV = _load_nav()


@pytest.fixture(scope="module")
def ui():
    """Import the UI modules the way `streamlit run ui/app.py` does, pointed at a port nothing listens on."""
    with pytest.MonkeyPatch.context() as mp:
        for name in ("VIGIL_API_URL", "VIGIL_DEMO_SHOP_HEALTH_URL"):
            mp.setenv(name, "http://127.0.0.1:9")
        mp.syspath_prepend(str(UI))
        import common
        import registry

        yield {"common": common, "registry": registry}
    for name in [m for m in sys.modules if m in ("common", "registry") or m == "views" or m.startswith("views.")]:
        sys.modules.pop(name, None)


def test_every_nav_entry_has_a_page_and_every_page_has_a_nav_entry(ui):
    nav_keys = NAV.all_page_keys()
    assert len(nav_keys) == len(set(nav_keys)), "a page appears twice in the sidebar"
    assert set(nav_keys) == set(ui["registry"].PAGES)


def test_every_page_has_a_guide_entry_and_it_points_at_a_real_guide_page():
    assert set(NAV.GUIDE_PAGES) == set(NAV.all_page_keys())
    for key, slug in NAV.GUIDE_PAGES.items():
        if slug is not None:
            assert slug == "index" or (GUIDE_SRC / f"{slug}.md").exists(), f"{key} -> {slug}"
    for _label, slug in NAV.GUIDE_LINKS:
        assert slug == "index" or (GUIDE_SRC / f"{slug}.md").exists(), slug


def test_every_level_architecture_and_reliability_guide_page_is_reachable_from_the_ui():
    reachable = {s for s in NAV.GUIDE_PAGES.values() if s} | {s for _label, s in NAV.GUIDE_LINKS}
    topics = {p.stem for p in GUIDE_SRC.glob("*.md") if re.fullmatch(r"[lar]\d+b?", p.stem)}
    assert topics, "no level/architecture/reliability pages found"
    assert topics <= reachable, sorted(topics - reachable)


def test_guide_url_shape(ui):
    common = ui["common"]
    assert common.guide_url("index") == f"{common.DOCS_URL}/index.html"
    assert common.guide_url("l0") == f"{common.DOCS_URL}/pages/l0.html"


def test_sections_follow_the_guide():
    names = [g.split(") ", 1)[1] for g in NAV.NAV_GROUPS]
    assert names == ["Start", "Levels", "Architectures", "Reliability", "Foundations", "Extensions", "Themes", "Projects"]
    reliability = NAV.NAV_GROUPS["4) Reliability"]
    assert [label.split(" — ")[0] for label in reliability] == [f"R{i}" for i in range(1, 10)]


def _render(key, ui_dir):  # runs inside AppTest, in its own script context, so it must be self-contained
    import sys as _sys

    _sys.path.insert(0, ui_dir)
    from registry import PAGES

    PAGES[key]()


@pytest.mark.parametrize("key", NAV.all_page_keys())
def test_every_page_renders_without_raising(key, ui):
    at = AppTest.from_function(_render, args=(key, str(UI)), default_timeout=30)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
