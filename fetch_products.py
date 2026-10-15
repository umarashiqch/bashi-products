#!/usr/bin/env python3
"""Pull all published products from bashi.pk's public WooCommerce Store API,
download each product's ~800px images into images/, and write products.json.
No credentials needed: the Store API only exposes data already visible on
the storefront."""

import json
import re
import urllib.request
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

API_BASE = "https://bashi.pk/wp-json/wc/store/v1/products"
PER_PAGE = 100
TARGET_WIDTH = 800
ROOT = Path(__file__).parent
OUTPUT_PATH = ROOT / "products.json"
IMAGES_DIR = ROOT / "images"


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


def pick_800px_url(image):
    """Pick the srcset entry closest to TARGET_WIDTH (preferring >= it),
    falling back to the full-size src if there's no srcset."""
    srcset = image.get("srcset") or ""
    candidates = []
    for entry in srcset.split(","):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.rsplit(" ", 1)
        if len(parts) != 2 or not parts[1].endswith("w"):
            continue
        url, width_str = parts
        try:
            width = int(width_str[:-1])
        except ValueError:
            continue
        candidates.append((width, url))

    if not candidates:
        return image["src"]

    at_or_above = [c for c in candidates if c[0] >= TARGET_WIDTH]
    if at_or_above:
        return min(at_or_above, key=lambda c: c[0])[1]
    return max(candidates, key=lambda c: c[0])[1]


def download_images(slug, images):
    """Download this product's images (skipping ones already on disk) and
    return the list of local paths (relative to the repo root, forward
    slashes) actually saved for it, the matching alt text for each, and the
    set of filenames now in use."""
    local_paths = []
    alts = []
    filenames = set()
    for index, image in enumerate(images, start=1):
        url = pick_800px_url(image)
        ext = Path(urlparse(url).path).suffix or ".webp"
        filename = f"{slug}-{index}{ext}"
        filenames.add(filename)
        dest = IMAGES_DIR / filename
        local_paths.append(f"images/{filename}")
        alts.append(image.get("alt") or "")
        if dest.exists():
            continue
        req = urllib.request.Request(url, headers={"User-Agent": "bashi-products-sync"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            dest.write_bytes(resp.read())
        print(f"Downloaded {filename}")
    return local_paths, alts, filenames


def simplify(product):
    slug = product["slug"]
    images = product.get("images", [])
    local_images, image_alts, filenames = download_images(slug, images)
    return {
        "id": product["id"],
        "name": product["name"],
        "slug": slug,
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
        "local_images": local_images,
        "image_alts": image_alts,
    }, filenames


def main():
    IMAGES_DIR.mkdir(exist_ok=True)

    page = 1
    all_products = []
    live_filenames = set()
    while True:
        products, total_pages = fetch_page(page)
        if not products:
            break
        for product in products:
            simplified, filenames = simplify(product)
            all_products.append(simplified)
            live_filenames |= filenames
        if page >= total_pages:
            break
        page += 1

    all_products.sort(key=lambda p: p["name"])
    OUTPUT_PATH.write_text(json.dumps(all_products, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(all_products)} products to {OUTPUT_PATH}")

    removed = 0
    for existing in IMAGES_DIR.iterdir():
        if existing.is_file() and existing.name not in live_filenames:
            existing.unlink()
            removed += 1
    print(f"Removed {removed} stale image file(s)")


if __name__ == "__main__":
    main()
