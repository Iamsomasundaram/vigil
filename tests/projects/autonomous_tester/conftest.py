"""These tests need the optional `tester` extra (FastAPI, PyYAML). Skip cleanly when absent."""

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("yaml")
