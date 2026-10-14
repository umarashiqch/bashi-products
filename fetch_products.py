#!/usr/bin/env python3
"""Pull all published products from bashi.pk's public WooCommerce Store API
and write them to products.json. No credentials needed: the Store API only
exposes data already visible on the storefront."""

import json
import re
import urllib.request
from html import unescape
from pathlib import Path

API_BASE = "https://bashi.pk/wp-json/wc/store/v1/products"
PER_PAGE = 100
OUTPUT_PATH = Path(__file__).parent / "products.json"


def strip_html(html):
    text = unescape(html or "")
    # Rank Math's FAQ block comment sometimes survives double-escaped, mixing
    # real "<p>" tags with entity-escaped quotes, so it can't be matched as a
    # well-formed HTML comment. Just drop everything from its start onward.
    marker = text.find("wp:rank-math")
    if marker != -1:
        tag_start = text.rfind("<", 0, marker)
        text = text[: tag_start if tag_start != -1 else marker]
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_page(page):
    url = f"{API_BASE}?per_page={PER_PAGE}&page={page}"
    req = urllib.request.Request(url, headers={"User-Agent": "bashi-products-sync"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        total_pages = int(resp.headers.get("X-WP-TotalPages", "1"))
        data = json.loads(resp.read().decode("utf-8"))
    return data, total_pages


def simplify(product):
    return {
        "id": product["id"],
        "name": product["name"],
        "slug": product["slug"],
        "sku": product.get("sku") or None,
        "permalink": product["permalink"],
        "on_sale": product.get("on_sale", False),
        "price": product["prices"]["price"],
        "regular_price": product["prices"]["regular_price"],
        "currency": product["prices"]["currency_code"],
        "in_stock": product.get("is_in_stock", True),
        "categories": [c["name"] for c in product.get("categories", [])],
        "description": strip_html(product.get("description", "")),
        "short_description": strip_html(product.get("short_description", "")),
        "images": [
            {"src": img["src"], "alt": img.get("alt", "")}
            for img in product.get("images", [])
        ],
    }


def main():
    page = 1
    all_products = []
    while True:
        products, total_pages = fetch_page(page)
        if not products:
            break
        all_products.extend(simplify(p) for p in products)
        if page >= total_pages:
            break
        page += 1

    all_products.sort(key=lambda p: p["name"])
    OUTPUT_PATH.write_text(json.dumps(all_products, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(all_products)} products to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
