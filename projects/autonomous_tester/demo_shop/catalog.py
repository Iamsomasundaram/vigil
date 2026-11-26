"""Generate the product catalog from the seed config and the active issues. Deterministic."""

from __future__ import annotations

from dataclasses import dataclass

from projects.autonomous_tester.demo_shop.config import ShopConfig, load_seed


@dataclass(frozen=True)
class Variant:
    name: str
    delta_cents: int


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    price_cents: int
    stock: int
    image: str | None
    variants: tuple[Variant, ...]

    def variant(self, name: str) -> Variant | None:
        return next((v for v in self.variants if v.name == name), None)

    def unit_price(self, variant_name: str) -> int:
        variant = self.variant(variant_name)
        return self.price_cents + (variant.delta_cents if variant else 0)


def build_catalog(cfg: ShopConfig) -> dict[str, Product]:
    """Products in seed order. Data issues change the data here, not the shop's behaviour."""
    out_of_stock = cfg.targets["D01"] if "D01" in cfg.active else None
    no_image = cfg.targets["D02"] if "D02" in cfg.active else None
    catalog: dict[str, Product] = {}
    for raw in load_seed()["products"]:
        sku = raw["sku"]
        catalog[sku] = Product(
            sku=sku,
            name=raw["name"],
            price_cents=int(raw["price_cents"]),
            stock=0 if sku == out_of_stock else int(raw["stock"]),
            image=None if sku == no_image else raw["image"],
            variants=tuple(Variant(v["name"], int(v["delta_cents"])) for v in raw["variants"]),
        )
    return catalog
