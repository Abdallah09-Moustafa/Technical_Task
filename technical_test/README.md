# Technical Test — Odoo 17

An Odoo 17 application that extends Point of Sale, Inventory, Website/eCommerce, and adds authenticated JSON endpoints for ROP (re-order point) and order data.

## Module information

| Property | Value |
|---|---|
| Technical name | `technical_test` |
| Version | `17.0.1.0.0` |
| License | LGPL-3 |
| Installable | Yes |
| Application | Yes |
| Dependencies | `base`, `product`, `stock`, `point_of_sale`, `website`, `website_sale`, `sale`, `mail`, `bus` |

The module adds its own files under `models/`, `controllers/`, `wizard/`, `security/`, `views/`, `static/`, and `tests/`. The manifest loads security before views and registers POS and website frontend assets in their Odoo asset bundles.

## Features

### Point of Sale

- Loads product stock quantity, product type, and ROP fields into the POS product data.
- Checks stockable order lines when the cashier attempts to pay. If a product has available quantity of **5 or less**, payment is blocked and an ROP alert is displayed.
- On that low-stock check, posts a notification to warehouse managers (or warehouse users if no manager group is available) and the system administrator.
- Requires a customer on payment, and accepts a phone or mobile number that starts with `+2`.
- Adds a **Cash now** button to the product screen. It selects the system administrator customer (marked by the POS loader) when it has a qualifying `+2` phone/mobile, selects a configured cash payment method, pays the order total, marks the order for invoicing, and enters the standard payment validation flow. Odoo handles order finalization and invoice generation.
- Adds the administrator’s partner to the POS partner data returned by the session loader, in addition to the configured limited partner list.

POS customizations are in `static/src/app/`; stock-check support is in `models/pos_session.py`. POS JS/XML assets are registered in `point_of_sale._assets_pos`.

### Inventory and product ROP data

- Extends `product.template` with:
  - `has_rop`: whether the product uses the ROP measure.
  - `rop_count`: the configured ROP count.
  - `same_rop_count`: a non-stored count of other products with the same positive ROP count.
- The matching-product count uses grouped aggregation rather than one query per product.
- Adds a product form smart button that opens products with the same ROP count.
- Adds an Inventory **ROP** menu with **ROP Products** (available quantity below 5) and **Products > ROP** (available quantity above 5) actions.
- Rejects outgoing transfers whose scheduled date is earlier than the current date in the user’s context.

Implementation: `models/product_template.py`, `models/stock_picking.py`, `views/product_template_views.xml`, and `views/inventory_menus.xml`.

### Website and eCommerce

- `/shop/rop` displays saleable storable products with available quantity below 5. It is available to authenticated internal users and is paginated.
- The low-stock page includes an **Update Product quantity** dialog. The update route is restricted to stock managers, validates the product/company, applies an inventory adjustment in the current company’s warehouse stock location, and sends a notification to other warehouse managers and the system administrator.
- `/shop/realtime-rop` displays saleable storable products with quantity above 5. Its data endpoint is polled by the page script every four seconds; the initial results and subsequent poll are limited to the requested page.
- `/rop-product` returns low-stock products as JSON to authenticated internal users.
- Website views and JSON product responses use pagination with a maximum of 100 rows per page.

Implementation: `controllers/website_rop.py`, `wizard/update_product_qty_wizard.py`, `views/website_rop_templates.xml`, and `static/src/js/website_rop.js`. Website JS/CSS are registered in `web.assets_frontend`.

### Authenticated JSON API

All API routes below require an authenticated Odoo user. Successful JSON responses include pagination metadata where applicable: `page`, `limit`, `total_count`, and `has_more`. The page size defaults to 100 and is capped at 100; `page` and `limit` must be positive integers.

| Route | Method | Purpose |
|---|---|---|
| `/api/orders` or `/api/v1/orders` | GET | Return sale and POS orders within `start_date` and `end_date` (date or ISO 8601 datetime). |
| `/api/products/rop` or `/api/v1/products/rop` | GET | Return products with `has_rop=True` and a positive `rop_count`. |
| `/api/product/<product_id>/rop` or `/api/v1/product/<product_id>/rop` | POST, PUT | Set the ROP values for a product. |
| `/api/product/rop` or `/api/v1/product/rop` | POST, PUT | Same update operation; accepts `product_id` in the request body or parameters. |
| `/api/pos/session/<session_id>/orders` or `/api/v1/pos/session/<session_id>/orders` | GET | Return POS orders for a session. |
| `/api/pos/orders` or `/api/v1/pos/orders` | GET | Same operation; accepts `session_id` as a parameter. |

The ROP update endpoint accepts a JSON object containing `product_id`, `rop_count`, and optional `has_rop`. ROP writes are limited to system administrators and stock managers. Date-range order queries accept `start_date` and `end_date`; both are required.

Implementation: `controllers/rest_api.py`.

### Stock quantity wizard

The **Update Product Quantity** wizard is bound to the product form. It displays the current on-hand quantity and lets a stock manager apply a non-negative integer quantity. It uses Odoo’s inventory adjustment mechanism, so the stock change is recorded through stock operations rather than by directly writing a quantity field. The wizard also sends update notifications.

Implementation: `wizard/update_product_qty_wizard.py` and `wizard/update_product_qty_wizard_views.xml`.

## Access control and company behavior

- Only members of `stock.group_stock_manager` have wizard ACLs and may execute inventory quantity updates through the website endpoint or wizard action.
- Stock updates do not use `sudo()`. Product company must either be shared or match the active company; the adjustment location is the active company warehouse’s stock location.
- The low-stock website view and `/rop-product` endpoint are limited to authenticated internal users.
- The real-time ROP page and its read-only data endpoint are public and expose saleable products with quantity above 5.
- ROP update APIs require a system administrator or stock manager.

## Installation and upgrade

1. Ensure the module’s parent directory is included in the Odoo `addons_path`.
2. Update the Apps list, then install **Technical Test - Odoo 17 Solution** (`technical_test`) from Apps.
3. To update an existing installation, restart Odoo with the module update option, for example:

   ```bash
   ./odoo-bin -d <database> -u technical_test --stop-after-init
   ```

The POS/eCommerce features also require their respective Odoo applications to be installed and configured. Cash now requires the system administrator (`base.user_admin`) to have a phone or mobile beginning with `+2`, plus a cash payment method configured for the POS.

## Tests

The module’s `tests/` package includes `TransactionCase` and `HttpCase` coverage for ROP counts, outgoing picking dates, stock quantity adjustments and access restrictions, POS low-stock notification, partner loading, API responses, and endpoint authentication. Its POS and website JavaScript components have a QUnit suite in `static/tests/unit/technical_test_pos_tests.js`, registered in the POS QUnit asset bundle. It covers ROP payment blocking, fallback behavior, customer phone validation, Cash now flows, and website quantity-modal input handling.

Run the module tests against a database with:

```bash
./odoo-bin -d <database> -u technical_test --test-enable --test-tags /technical_test --stop-after-init
```

The module test command above also launches the browser-backed POS QUnit suite. To run only that browser test:

```bash
./odoo-bin -d <database> -u technical_test --test-enable --test-tags /technical_test:TestTechnicalTestPosJs.test_pos_js --stop-after-init
```

## File map

| Path | Responsibility |
|---|---|
| `models/product_template.py` | Product ROP fields, matching count, smart-button action |
| `models/stock_picking.py` | Outgoing scheduled-date constraint |
| `models/pos_session.py` | POS product/partner loading and low-stock notifications |
| `controllers/website_rop.py` | Website ROP pages, stock update route, and `/rop-product` |
| `controllers/rest_api.py` | Authenticated order and product APIs |
| `wizard/update_product_qty_wizard.py` | Authorized inventory adjustment and notifications |
| `security/ir.model.access.csv` | Wizard access for stock managers |
| `views/` and `wizard/` | Product, Inventory menu, website, and wizard views |
| `static/src/app/` | POS Cash now, phone, and low-stock behavior |
| `static/src/js/`, `static/src/css/` | Website polling and styling |
| `tests/` | Odoo transaction and HTTP tests |
