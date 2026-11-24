# Purchase Price Change Warning

Purchase Price Change Warning is a lightweight Odoo 20 Community addon that helps purchasers notice unexpected vendor price changes while preparing an RFQ or purchase order.

## Features

- Compares a line with the latest confirmed purchase for the same product and commercial vendor.
- Keeps comparisons inside the current company and respects standard Purchase access rules.
- Converts the historical unit price to the current line UoM and PO currency.
- Shows the previous price, signed change percentage, and an informative non-blocking warning.
- Offers company-specific enablement, threshold, and increase-only/increase-or-decrease settings.
- Uses a deterministic, limited history query and non-stored computed fields.

## Installation

1. Add this directory to an Odoo 20 addons path.
2. Update the Apps list.
3. Install **Purchase Price Change Warning**.

The only dependency is Odoo's standard `purchase` addon.

## Odoo Apps publication

The public source repository is:

`https://github.com/sakobulghurjian/purchase_price_change_warning`

Register the Odoo 20 branch in Odoo Apps with this SSH repository URL:

`ssh://git@github.com/sakobulghurjian/purchase_price_change_warning#20.0`

The repository is public, so Odoo Apps can read it without private-repository credentials. A read-only collaborator invitation has also been sent to the official GitHub account `online-odoo`; the invitation remains subject to acceptance by that account.

## Configuration

Open **Purchase > Configuration > Settings > Purchase Price Change Warning**. The feature is enabled by default with an inclusive 10% threshold and **Price Increase Only** mode.

## Behavior

The warning is informational. It does not change purchase permissions, create an approval workflow, or block saving, sending, or confirming an order.

Historical prices use the gross tax-exclusive `price_unit` before line discount. Currency conversion uses the historical purchase confirmation date (falling back to its order date).

## License

LGPL-3. See `LICENSE`.
