"""Load the seed config and turn a profile name into a ShopConfig (which issues are switched on)."""

from __future__ import annotations

import yaml
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from projects.autonomous_tester.evals.answer_key import load_answer_key

SEED_FILE = Path(__file__).parent / "seed.yaml"

# Every seeded issue the shop code knows how to switch on. A test keeps this equal to the answer key.
ISSUE_IDS = frozenset({"B01", "B02", "B03", "B04", "B05", "D01", "D02", "E01", "E02", "A01", "X01", "X02", "X03"})


@dataclass(frozen=True)
class ShopConfig:
    profile: str
    shop_version: int
    active: frozenset[str]
    targets: dict[str, str]
    slow_seconds: float


@lru_cache(maxsize=1)
def load_seed() -> dict:
    return yaml.safe_load(SEED_FILE.read_text(encoding="utf-8"))


def profile_names() -> list[str]:
    return list(load_seed()["profiles"])


def build_config(profile: str = "clean", slow_seconds: float | None = None) -> ShopConfig:
    seed = load_seed()
    if profile not in seed["profiles"]:
        raise ValueError(f"unknown profile {profile!r}; choose from {profile_names()}")
    active = frozenset(issue.id for issue in load_answer_key().active(profile))
    return ShopConfig(
        profile=profile,
        shop_version=int(seed["profiles"][profile]["shop_version"]),
        active=active,
        targets=dict(seed["targets"]),
        slow_seconds=float(seed["slow_seconds"] if slow_seconds is None else slow_seconds),
    )
