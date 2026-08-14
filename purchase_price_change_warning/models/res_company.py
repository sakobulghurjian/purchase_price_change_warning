from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    purchase_price_change_warning_enabled = fields.Boolean(
        string="Enable Purchase Price Change Warning",
        default=True,
    )
    purchase_price_change_warning_threshold = fields.Float(
        string="Warning Threshold (%)",
        default=10.0,
    )
    purchase_price_change_warning_type = fields.Selection(
        selection=[
            ("increase", "Price Increase Only"),
            ("both", "Price Increase or Decrease"),
        ],
        string="Warning Type",
        required=True,
        default="increase",
    )

    @api.constrains("purchase_price_change_warning_threshold")
    def _check_purchase_price_change_warning_threshold(self):
        for company in self:
            if company.purchase_price_change_warning_threshold < 0:
                raise ValidationError(_("The purchase price warning threshold cannot be negative."))

