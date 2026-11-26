"""
The demo shop and its answer key must agree: every seeded issue is really observable under
each profile that switches it on, and absent everywhere else (above all under ``clean``).
"""

from __future__ import annotations

import re
import time

import pytest
from fastapi.testclient import TestClient

from projects.autonomous_tester.demo_shop.app import create_app
from projects.autonomous_tester.demo_shop.catalog import build_catalog
from projects.autonomous_tester.demo_shop.config import ISSUE_IDS, build_config, profile_names
from projects.autonomous_tester.demo_shop.pages import TESTIDS
from projects.autonomous_tester.evals.answer_key import load_answer_key

SLOW = 0.3  # seconds; the shop's slow-response issue, shortened for tests


class Shop:
    """A tiny test driver: one shop instance, one session, version-aware test ids."""

    def __init__(self, profile: str):
        self.profile = profile
        self.cfg = build_config(profile, slow_seconds=SLOW)
        self.client = TestClient(create_app(profile, slow_seconds=SLOW))
        self.ids = TESTIDS[self.cfg.shop_version]

    def text(self, html: str, testid: str) -> list[str]:
        return re.findall(rf'data-testid="{re.escape(testid)}"[^>]*>([^<]*)<', html)

    def add(self, sku: str, variant: str | None = None, quantity: int = 1):
        data = {"sku": sku, "quantity": str(quantity)}
        if variant:
            data["variant"] = variant
        return self.client.post("/cart/add", data=data)

    def badge(self, html: str) -> int | None:
        found = self.text(html, "cart-badge")
        return int(found[0]) if found else None


# ─── clean shop works end to end ──────────────────────────────────────────────────

def test_clean_shop_flow_is_correct():
    shop = Shop("clean")
    assert shop.client.get("/health").json() == {"status": "ok"}
    index = shop.client.get("/").text
    assert index.count('data-testid="product-card"') == 6

    page = shop.add("SKU-001", "L", 2)  # follows the redirect back to the product page
    assert shop.text(page.text, "added-notice") == ["Added to cart"]
    assert shop.badge(page.text) == 2

    cart = shop.client.get("/cart").text
    assert shop.text(cart, "line-qty") == ["2"]
    assert shop.text(cart, "line-price") == ["$91.99"]
    assert shop.text(cart, shop.ids["subtotal"]) == ["$183.98"]

    after = shop.client.post("/cart/remove", data={"sku": "SKU-001", "variant": "L"}).text
    assert shop.text(after, "cart-empty") == ["Your cart is empty"]
    assert shop.text(after, shop.ids["subtotal"]) == ["$0.00"]


def test_clean_shop_has_no_data_problems_and_no_extras():
    shop = Shop("clean")
    catalog = build_catalog(shop.cfg)
    assert all(p.stock > 0 and p.image for p in catalog.values())
    page = shop.client.get("/product/SKU-004").text
    assert "console.error" not in page and "promo-banner" not in page
    assert 'alt="Headlamp"' in page


def test_unknown_inputs_are_rejected_not_crashed():
    shop = Shop("clean")
    assert shop.client.get("/product/NOPE").status_code == 404
    assert shop.add("NOPE").status_code == 404
    assert shop.add("SKU-001", "XXL").status_code == 400
    assert shop.add("SKU-001", quantity=0).status_code == 400
    assert shop.client.get("/img/../secret").status_code in (404, 405)
    assert shop.client.get("/img/backpack.svg").headers["content-type"].startswith("image/svg+xml")


def test_unknown_profile_is_an_error():
    with pytest.raises(ValueError):
        build_config("nonsense")


def test_catalog_is_deterministic():
    a = build_catalog(build_config("all_bugs"))
    b = build_catalog(build_config("all_bugs"))
    assert a == b


def test_health_does_not_reveal_the_profile():
    assert Shop("all_bugs").client.get("/health").json() == {"status": "ok"}


# ─── each seeded issue: present when active, absent otherwise ─────────────────────────

def _price_text(shop: Shop, sku: str) -> str | None:
    found = shop.text(shop.client.get(f"/product/{sku}").text, shop.ids["price"])
    return found[0] if found else None


def b01(shop: Shop) -> bool:
    page_price = _price_text(shop, "SKU-002")
    shop.add("SKU-002")
    cart = shop.client.get("/cart")
    cart_price = shop.text(cart.text, "line-price")
    return bool(page_price and cart_price) and cart_price[0] != page_price


def b02(shop: Shop) -> bool:
    page = shop.client.get("/product/SKU-001").text
    match = re.search(r'<option value="L" data-price-cents="(\d+)"', page)
    expected = build_catalog(build_config("clean"))["SKU-001"].unit_price("L")
    return bool(match) and int(match.group(1)) != expected


def b03(shop: Shop) -> bool:
    shop.add("SKU-003", quantity=3)
    qty = shop.text(shop.client.get("/cart").text, "line-qty")
    return bool(qty) and qty[0] != "3"


def b04(shop: Shop) -> bool:
    shop.add("SKU-003")
    after = shop.client.post("/cart/remove", data={"sku": "SKU-003", "variant": "default"}).text
    subtotal = shop.text(after, shop.ids["subtotal"])
    return bool(subtotal) and subtotal[0] != "$0.00"


def b05(shop: Shop) -> bool:
    page = shop.add("SKU-005").text
    cart = shop.client.get("/cart").text
    return shop.badge(page) == 1 and shop.ids["line"] not in cart


def d01(shop: Shop) -> bool:
    return shop.add("SKU-004").status_code == 409


def d02(shop: Shop) -> bool:
    return 'data-testid="product-image"' not in shop.client.get("/product/SKU-006").text


def e01(shop: Shop) -> bool:
    return shop.client.get("/cart").status_code == 503


def e02(shop: Shop) -> bool:
    start = time.perf_counter()
    shop.client.get("/product/SKU-001")
    return time.perf_counter() - start >= SLOW


def a01(shop: Shop) -> bool:
    page = shop.client.get("/product/SKU-001").text
    return 'data-testid="add-to-cart"' not in page and 'data-testid="btn-add"' in page


def x01(shop: Shop) -> bool:
    return "console.error" in shop.client.get("/product/SKU-001").text


def x02(shop: Shop) -> bool:
    page = shop.client.get("/product/SKU-001").text
    return 'data-testid="promo-banner"' in page and "max-width:420px" in page


def x03(shop: Shop) -> bool:
    return re.search(r"<img(?![^>]*\balt=)", shop.client.get("/product/SKU-001").text) is not None


SYMPTOMS = {
    "B01": b01, "B02": b02, "B03": b03, "B04": b04, "B05": b05, "D01": d01, "D02": d02,
    "E01": e01, "E02": e02, "A01": a01, "X01": x01, "X02": x02, "X03": x03,
}


def test_every_issue_has_a_symptom_check():
    assert set(SYMPTOMS) == ISSUE_IDS == {i.id for i in load_answer_key().issues}


@pytest.mark.parametrize("profile", profile_names())
@pytest.mark.parametrize("issue_id", sorted(SYMPTOMS))
def test_issue_is_observable_exactly_where_the_key_says(issue_id, profile):
    issue = next(i for i in load_answer_key().issues if i.id == issue_id)
    expected = profile in issue.active_in
    observed = SYMPTOMS[issue_id](Shop(profile))
    assert observed is expected, f"{issue_id} under {profile}: expected {expected}, observed {observed}"


def test_clean_profile_switches_nothing_on():
    assert build_config("clean").active == frozenset()


def test_v2_markup_is_a_pure_rename():
    """Same flow, same numbers; only the test ids differ."""
    v1, v2 = Shop("clean"), Shop("v2_markup")
    for shop in (v1, v2):
        shop.add("SKU-001", "L", 2)
    cart1, cart2 = v1.client.get("/cart").text, v2.client.get("/cart").text
    assert v1.text(cart1, "line-qty") == v2.text(cart2, "line-qty") == ["2"]
    assert v1.text(cart1, v1.ids["subtotal"]) == v2.text(cart2, v2.ids["subtotal"]) == ["$183.98"]
    assert v1.ids != v2.ids
