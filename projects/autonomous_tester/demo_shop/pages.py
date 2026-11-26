"""
HTML for the demo shop, built with plain f-strings (no template dependency).

Elements a test needs carry a ``data-testid``. Shop version 2 renames four of them and moves
the price element, which is what the automation issue (A01) is made of; behaviour is identical.
"""

from __future__ import annotations

from html import escape

from projects.autonomous_tester.demo_shop.catalog import Product
from projects.autonomous_tester.demo_shop.config import ShopConfig

# Test ids that differ between shop versions. Every other test id is the same in both.
TESTIDS = {
    1: {"add": "add-to-cart", "price": "price", "line": "cart-line", "subtotal": "cart-subtotal"},
    2: {"add": "btn-add", "price": "product-price", "line": "line-item", "subtotal": "order-subtotal"},
}

_CSS = (
    "body{font-family:system-ui,sans-serif;margin:0;color:#1d1d1f}"
    "header{display:flex;gap:1.5rem;padding:.75rem 1rem;background:#f2f2f4}"
    "main{padding:1rem;max-width:40rem}"
    "table{border-collapse:collapse}td,th{padding:.25rem .75rem;text-align:left}"
    "button{padding:.5rem 1rem}"
)

# Issue X02: below 420px wide, a fixed banner sits over the middle of the page.
_BANNER_CSS = "@media (max-width:420px){.promo-banner{position:fixed;left:0;right:0;top:35%;bottom:0;background:#fffbe6;z-index:10}}"


def tid(cfg: ShopConfig, key: str) -> str:
    return TESTIDS[cfg.shop_version][key]


def money(cents: int) -> str:
    return f"${cents // 100:,}.{cents % 100:02d}"


def layout(cfg: ShopConfig, title: str, body: str, badge: int, extra_head: str = "") -> str:
    banner = ""
    if "X02" in cfg.active:
        banner = '<div data-testid="promo-banner" class="promo-banner">Free shipping on orders over $50</div>'
        extra_head += f"<style>{_BANNER_CSS}</style>"
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(title)} - Demo Shop</title><style>{_CSS}</style>{extra_head}</head><body>"
        '<header><a href="/" data-testid="home-link">Demo Shop</a>'
        f'<a href="/cart" data-testid="cart-link">Cart <span data-testid="cart-badge">{badge}</span></a></header>'
        f"{banner}<main>{body}</main></body></html>"
    )


def index_page(cfg: ShopConfig, catalog: dict[str, Product], badge: int) -> str:
    items = "".join(
        f'<li data-testid="product-card"><a href="/product/{p.sku}">{escape(p.name)}</a> '
        f"<span>{money(p.price_cents)}</span></li>"
        for p in catalog.values()
    )
    return layout(cfg, "Products", f"<h1>Products</h1><ul>{items}</ul>", badge)


def product_page(cfg: ShopConfig, product: Product, badge: int, added: bool = False) -> str:
    first = product.variants[0]
    shown_price = product.unit_price(first.name)

    # Issue B02: the larger variant carries the base price, so the displayed price never updates.
    stale_variant = product.variants[-1].name if "B02" in cfg.active and cfg.targets["B02"] == product.sku else None
    options = "".join(
        f'<option value="{escape(v.name)}" data-price-cents="'
        f'{product.price_cents if v.name == stale_variant else product.unit_price(v.name)}">{escape(v.name)}</option>'
        for v in product.variants
    )
    if product.image:
        # Issue X03: images have no alt text.
        alt = "" if "X03" in cfg.active else f' alt="{escape(product.name)}"'
        image = f'<img data-testid="product-image" src="/img/{product.image}" width="200" height="200"{alt}>'
    else:
        image = '<p data-testid="image-missing">No image available</p>'

    in_stock = product.stock > 0
    disabled = "" if in_stock else " disabled"
    status = "In stock" if in_stock else "Out of stock"
    price_html = f'<p><span id="price" data-testid="{tid(cfg, "price")}">{money(shown_price)}</span></p>'
    notice = '<p data-testid="added-notice">Added to cart</p>' if added else ""

    # Shop version 2 moves the price below the form, inside a new wrapper.
    form = (
        '<form method="post" action="/cart/add">'
        f'<input type="hidden" name="sku" value="{product.sku}">'
        f'<select id="variant" name="variant" data-testid="variant-select">{options}</select> '
        '<input type="number" name="quantity" value="1" min="1" max="99" data-testid="quantity"> '
        f'<button type="submit" data-testid="{tid(cfg, "add")}"{disabled}>Add to cart</button>'
        "</form>"
    )
    buy = f"{price_html}{form}" if cfg.shop_version == 1 else f'<div class="buybox">{form}</div>{price_html}'
    update_price_js = (
        "<script>(function(){var v=document.getElementById('variant'),p=document.getElementById('price');"
        "v.addEventListener('change',function(){var n=parseInt(v.options[v.selectedIndex].getAttribute('data-price-cents'),10);"
        "p.textContent='$'+Math.floor(n/100).toLocaleString()+'.'+('0'+(n%100)).slice(-2);});})();</script>"
    )
    body = (
        f'<h1 data-testid="product-name">{escape(product.name)}</h1>{image}'
        f'<p data-testid="stock-status">{status}</p>{notice}{buy}{update_price_js}'
    )
    # Issue X01: a console error on every product page load.
    script = '<script>console.error("Failed to load recommendations widget");</script>' if "X01" in cfg.active else ""
    return layout(cfg, product.name, body + script, badge)


def cart_page(cfg: ShopConfig, lines: list[dict], subtotal_cents: int, badge: int) -> str:
    if not lines:
        content = '<p data-testid="cart-empty">Your cart is empty</p>'
    else:
        rows = "".join(
            f'<tr data-testid="{tid(cfg, "line")}" data-sku="{line["sku"]}">'
            f'<td>{escape(line["name"])} ({escape(line["variant"])})</td>'
            f'<td data-testid="line-qty">{line["qty"]}</td>'
            f'<td data-testid="line-price">{money(line["unit_cents"])}</td>'
            '<td><form method="post" action="/cart/remove">'
            f'<input type="hidden" name="sku" value="{line["sku"]}">'
            f'<input type="hidden" name="variant" value="{escape(line["variant"])}">'
            '<button type="submit" data-testid="remove-item">Remove</button></form></td></tr>'
            for line in lines
        )
        content = f"<table><tr><th>Item</th><th>Qty</th><th>Price</th><th></th></tr>{rows}</table>"
    subtotal = f'<p>Subtotal: <span data-testid="{tid(cfg, "subtotal")}">{money(subtotal_cents)}</span></p>'
    return layout(cfg, "Cart", f"<h1>Your cart</h1>{content}{subtotal}", badge)


def image_svg(name: str) -> str:
    label = escape(name.rsplit(".", 1)[0])
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200">'
        '<rect width="200" height="200" fill="#dfe3e8"/>'
        f'<text x="100" y="105" text-anchor="middle" font-family="sans-serif" font-size="16">{label}</text></svg>'
    )
