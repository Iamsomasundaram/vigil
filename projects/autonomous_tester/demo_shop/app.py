"""
The demo shop: a tiny storefront whose behaviour is switched by a profile.

    python -m projects.autonomous_tester.demo_shop --profile all_bugs --port 8100

Routes: ``/`` list, ``/product/{sku}``, ``POST /cart/add``, ``/cart``, ``POST /cart/remove``,
``/img/{name}`` and ``/health``. The cart is in memory, keyed by a session cookie.

Seeded issues are implemented inline and marked with their id (B01, D02, ...), so a reader
can see exactly what each one changes. ``/health`` deliberately does not reveal the profile.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from dataclasses import dataclass, field
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from urllib.parse import parse_qs

from projects.autonomous_tester.demo_shop import pages
from projects.autonomous_tester.demo_shop.catalog import build_catalog
from projects.autonomous_tester.demo_shop.config import build_config

_IMAGE_NAME = re.compile(r"^[a-z0-9_.-]+$")


@dataclass
class Line:
    sku: str
    variant: str
    qty: int


@dataclass
class Cart:
    lines: list[Line] = field(default_factory=list)
    phantom: int = 0  # items counted in the header badge that never reached the cart (B05)

    def count(self) -> int:
        return sum(line.qty for line in self.lines) + self.phantom


def create_app(profile: str = "clean", *, slow_seconds: float | None = None) -> FastAPI:
    cfg = build_config(profile, slow_seconds)
    catalog = build_catalog(cfg)
    carts: dict[str, Cart] = {}
    app = FastAPI(title="Vigil Demo Shop", docs_url=None, redoc_url=None, openapi_url=None)

    # ─── helpers ──────────────────────────────────────────────────────────────────
    def session(request: Request) -> tuple[str, Cart, bool]:
        sid = request.cookies.get("shop_session")
        is_new = sid is None or sid not in carts
        if is_new:
            sid = uuid.uuid4().hex
            carts[sid] = Cart()
        return sid, carts[sid], is_new

    def reply(response: Response, sid: str, is_new: bool) -> Response:
        if is_new:
            response.set_cookie("shop_session", sid, httponly=True, samesite="lax")
        return response

    def html(content: str, sid: str, is_new: bool, status: int = 200) -> Response:
        return reply(HTMLResponse(content, status_code=status), sid, is_new)

    def cart_down() -> Response | None:
        if "E01" in cfg.active:  # E01: the cart is unavailable
            return HTMLResponse("<h1>Service Unavailable</h1>", status_code=503)
        return None

    async def form(request: Request) -> dict[str, str]:
        body = (await request.body()).decode("utf-8", "replace")
        return {k: v[0] for k, v in parse_qs(body, keep_blank_values=True).items()}

    def line_views(cart: Cart) -> list[dict]:
        views = []
        for line in cart.lines:
            product = catalog[line.sku]
            unit = product.unit_price(line.variant)
            if "B01" in cfg.active and line.sku == cfg.targets["B01"]:
                unit -= 1  # B01: the cart price is one cent lower than the product page
            views.append({"sku": line.sku, "name": product.name, "variant": line.variant, "qty": line.qty, "unit_cents": unit})
        return views

    def subtotal(views: list[dict]) -> int:
        return sum(v["unit_cents"] * v["qty"] for v in views)

    # ─── routes ───────────────────────────────────────────────────────────────────
    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> Response:
        sid, cart, is_new = session(request)
        return html(pages.index_page(cfg, catalog, cart.count()), sid, is_new)

    @app.get("/product/{sku}", response_class=HTMLResponse)
    async def product(sku: str, request: Request, added: int = 0) -> Response:
        if "E02" in cfg.active:  # E02: product pages respond slowly
            await asyncio.sleep(cfg.slow_seconds)
        item = catalog.get(sku)
        if item is None:
            return HTMLResponse("<h1>Not found</h1>", status_code=404)
        sid, cart, is_new = session(request)
        return html(pages.product_page(cfg, item, cart.count(), added=bool(added)), sid, is_new)

    @app.post("/cart/add")
    async def cart_add(request: Request) -> Response:
        if (down := cart_down()) is not None:
            return down
        data = await form(request)
        item = catalog.get(data.get("sku", ""))
        if item is None:
            return HTMLResponse("<h1>Unknown product</h1>", status_code=404)
        variant = data.get("variant") or item.variants[0].name
        if item.variant(variant) is None:
            return HTMLResponse("<h1>Unknown variant</h1>", status_code=400)
        try:
            qty = int(data.get("quantity", "1"))
        except ValueError:
            return HTMLResponse("<h1>Invalid quantity</h1>", status_code=400)
        if not 1 <= qty <= 99:
            return HTMLResponse("<h1>Invalid quantity</h1>", status_code=400)
        if item.stock < qty:
            return HTMLResponse("<h1>Out of stock</h1>", status_code=409)

        sid, cart, is_new = session(request)
        if "B03" in cfg.active and qty >= 3:
            qty -= 1  # B03: quantity 3 or more adds one too few
        if "B05" in cfg.active and item.sku == cfg.targets["B05"]:
            cart.phantom += qty  # B05: counted in the badge, never added to the cart
        else:
            existing = next((x for x in cart.lines if x.sku == item.sku and x.variant == variant), None)
            if existing:
                existing.qty += qty
            else:
                cart.lines.append(Line(item.sku, variant, qty))
        return reply(RedirectResponse(f"/product/{item.sku}?added=1", status_code=303), sid, is_new)

    @app.get("/cart", response_class=HTMLResponse)
    async def cart_view(request: Request) -> Response:
        if (down := cart_down()) is not None:
            return down
        sid, cart, is_new = session(request)
        views = line_views(cart)
        return html(pages.cart_page(cfg, views, subtotal(views), cart.count()), sid, is_new)

    @app.post("/cart/remove", response_class=HTMLResponse)
    async def cart_remove(request: Request) -> Response:
        if (down := cart_down()) is not None:
            return down
        data = await form(request)
        sid, cart, is_new = session(request)
        stale = subtotal(line_views(cart))
        cart.lines = [x for x in cart.lines if not (x.sku == data.get("sku") and x.variant == data.get("variant"))]
        views = line_views(cart)
        shown = stale if "B04" in cfg.active else subtotal(views)  # B04: subtotal not refreshed after removal
        return html(pages.cart_page(cfg, views, shown, cart.count()), sid, is_new)

    @app.get("/img/{name}")
    async def image(name: str) -> Response:
        if not _IMAGE_NAME.match(name):
            return Response(status_code=404)
        return Response(pages.image_svg(name), media_type="image/svg+xml")

    return app
