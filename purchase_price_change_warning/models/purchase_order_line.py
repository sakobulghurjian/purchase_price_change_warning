from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.tools import format_amount, format_date
from odoo.tools.float_utils import float_compare, float_is_zero


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    previous_purchase_price = fields.Monetary(
        string="Previous Price",
        currency_field="currency_id",
        compute="_compute_purchase_price_comparison",
    )
    price_change_percentage = fields.Float(
        string="Price Change (%)",
        compute="_compute_purchase_price_comparison",
        digits=(16, 2),
    )
    price_change_display = fields.Char(
        string="Change %",
        compute="_compute_purchase_price_comparison",
    )
    previous_purchase_order_id = fields.Many2one(
        comodel_name="purchase.order",
        string="Previous Purchase",
        compute="_compute_purchase_price_comparison",
    )
    previous_purchase_date = fields.Datetime(
        string="Previous Purchase Date",
        compute="_compute_purchase_price_comparison",
    )
    previous_purchase_quantity = fields.Float(
        string="Previous Quantity",
        compute="_compute_purchase_price_comparison",
        digits="Product Unit",
    )
    previous_purchase_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Previous Unit",
        compute="_compute_purchase_price_comparison",
    )
    previous_purchase_currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Previous Currency",
        compute="_compute_purchase_price_comparison",
    )
    purchase_price_change_warning = fields.Boolean(
        string="Price Change Warning",
        compute="_compute_purchase_price_comparison",
    )
    purchase_price_change_warning_icon = fields.Char(
        string="Warning",
        compute="_compute_purchase_price_comparison",
    )
    purchase_price_change_warning_message = fields.Html(
        string="Purchase Price Change Warning",
        compute="_compute_purchase_price_comparison",
        sanitize=True,
    )

    @api.depends(
        "order_id.partner_id",
        "order_id.currency_id",
        "order_id.company_id",
        "order_id.company_id.purchase_price_change_warning_enabled",
        "order_id.company_id.purchase_price_change_warning_threshold",
        "order_id.company_id.purchase_price_change_warning_type",
        "product_id",
        "uom_id",
        "product_qty",
        "price_unit",
    )
    @api.depends_context("uid", "allowed_company_ids")
    def _compute_purchase_price_comparison(self):
        for line in self:
            line._reset_purchase_price_comparison()
            if not line._can_compare_purchase_price():
                continue

            previous_line = line._find_previous_purchase_line()
            if not previous_line or float_is_zero(previous_line.price_unit, precision_digits=12):
                continue

            previous_price = line._normalize_previous_price(previous_line)
            if float_is_zero(previous_price, precision_digits=12):
                continue

            change = ((line.price_unit - previous_price) / previous_price) * 100.0
            warning = line._is_purchase_price_warning(change)
            previous_date = previous_line.order_id.date_approve or previous_line.order_id.date_order

            line.previous_purchase_price = previous_price
            line.price_change_percentage = change
            line.price_change_display = f"{change:+.2f}%"
            line.previous_purchase_order_id = previous_line.order_id
            line.previous_purchase_date = previous_date
            line.previous_purchase_quantity = previous_line.product_qty
            line.previous_purchase_uom_id = previous_line.uom_id
            line.previous_purchase_currency_id = previous_line.currency_id
            line.purchase_price_change_warning = warning
            line.purchase_price_change_warning_icon = "⚠" if warning else False
            if warning:
                line.purchase_price_change_warning_message = line._get_purchase_price_warning_message()

    def _reset_purchase_price_comparison(self):
        self.previous_purchase_price = False
        self.price_change_percentage = False
        self.price_change_display = False
        self.previous_purchase_order_id = False
        self.previous_purchase_date = False
        self.previous_purchase_quantity = False
        self.previous_purchase_uom_id = False
        self.previous_purchase_currency_id = False
        self.purchase_price_change_warning = False
        self.purchase_price_change_warning_icon = False
        self.purchase_price_change_warning_message = False

    def _can_compare_purchase_price(self):
        self.ensure_one()
        return bool(
            not self.display_type
            and self.product_id
            and self.uom_id
            and self.order_id.partner_id
            and self.currency_id
            and self.company_id
            and self.company_id.purchase_price_change_warning_enabled
        )

    def _find_previous_purchase_line(self):
        self.ensure_one()
        commercial_vendor = self.order_id.partner_id.commercial_partner_id
        order_domain = [
            ("partner_id.commercial_partner_id", "=", commercial_vendor.id),
            ("company_id", "=", self.company_id.id),
            ("state", "=", "purchase"),
            ("order_line.product_id", "=", self.product_id.id),
        ]
        if self.order_id.id:
            order_domain.append(("id", "!=", self.order_id.id))
        previous_order = self.env["purchase.order"].search(
            order_domain,
            order="date_approve desc, date_order desc, id desc",
            limit=1,
        )
        if not previous_order:
            return self.env["purchase.order.line"]
        return self.env["purchase.order.line"].search(
            [
                ("order_id", "=", previous_order.id),
                ("product_id", "=", self.product_id.id),
                ("display_type", "=", False),
            ],
            order="id desc",
            limit=1,
        )

    def _normalize_previous_price(self, previous_line):
        self.ensure_one()
        price = previous_line.uom_id._compute_price(
            previous_line.price_unit,
            self.uom_id,
        )
        conversion_date = fields.Date.to_date(
            previous_line.order_id.date_approve or previous_line.order_id.date_order
        )
        return previous_line.currency_id._convert(
            price,
            self.currency_id,
            self.company_id,
            conversion_date,
            round=False,
        )

    def _is_purchase_price_warning(self, change):
        self.ensure_one()
        company = self.company_id
        if not company.purchase_price_change_warning_enabled:
            return False
        compared_change = abs(change) if company.purchase_price_change_warning_type == "both" else change
        return float_compare(
            compared_change,
            company.purchase_price_change_warning_threshold,
            precision_digits=6,
        ) >= 0

    def _get_purchase_price_warning_message(self):
        self.ensure_one()
        title = _("Purchase Price Increased")
        if self.price_change_percentage < 0:
            title = _("Purchase Price Decreased")
        values = {
            "title": escape(title),
            "previous": escape(format_amount(self.env, self.previous_purchase_price, self.currency_id)),
            "current": escape(format_amount(self.env, self.price_unit, self.currency_id)),
            "change": escape(self.price_change_display),
            "purchase": escape(self.previous_purchase_order_id.display_name),
            "date": escape(format_date(self.env, fields.Date.to_date(self.previous_purchase_date))),
        }
        return Markup(
            "<strong>%(title)s</strong><br/>"
            "%(previous_label)s: %(previous)s<br/>"
            "%(current_label)s: %(current)s<br/>"
            "%(change_label)s: %(change)s<br/>"
            "%(purchase_label)s: %(purchase)s<br/>"
            "%(date_label)s: %(date)s"
        ) % {
            **values,
            "previous_label": escape(_("Previous Price")),
            "current_label": escape(_("Current Price")),
            "change_label": escape(_("Change")),
            "purchase_label": escape(_("Previous Purchase")),
            "date_label": escape(_("Previous Purchase Date")),
        }
