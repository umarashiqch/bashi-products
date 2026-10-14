# bashi-products

Daily snapshot of published products from [bashi.pk](https://bashi.pk), pulled from
WooCommerce's public Store API (`/wp-json/wc/store/v1/products`) — no credentials
involved, it's the same data already visible on the storefront.

- `fetch_products.py` fetches every product and writes `products.json`.
- `.github/workflows/sync.yml` runs the script once a day (and on manual dispatch)
  and commits `products.json` if anything changed.

Each entry in `products.json` has: id, name, slug, sku, permalink, price/regular
price/currency, sale and stock status, categories, description, short description,
and image URLs with alt text.
