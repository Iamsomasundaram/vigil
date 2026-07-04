"""CI-light validation that the learning notebooks are well-formed.

Parses each notebook as JSON (no execution, no network) and checks the basic
nbformat-4 structure. This guards against a notebook being committed broken.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

NOTEBOOKS_DIR = Path(__file__).resolve().parent.parent / "notebooks"
NOTEBOOKS = sorted(NOTEBOOKS_DIR.glob("*.ipynb"))


def test_notebooks_exist():
    assert len(NOTEBOOKS) >= 4, "Expected at least 4 learning notebooks"


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_is_valid_nbformat(path: Path):
    nb = json.loads(path.read_text(encoding="utf-8"))
    assert nb.get("nbformat") == 4
    assert isinstance(nb.get("cells"), list) and nb["cells"], "notebook has no cells"
    for cell in nb["cells"]:
        assert cell.get("cell_type") in {"markdown", "code"}
        assert isinstance(cell.get("source"), list)
        if cell["cell_type"] == "code":
            # Code cells must carry the keys Jupyter expects.
            assert "outputs" in cell
            assert "execution_count" in cell
