from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    purchase_price_change_warning_enabled = fields.Boolean(
        related="company_id.purchase_price_change_warning_enabled",
        readonly=False,
    )
    purchase_price_change_warning_threshold = fields.Float(
        related="company_id.purchase_price_change_warning_threshold",
        readonly=False,
    )
    purchase_price_change_warning_type = fields.Selection(
        related="company_id.purchase_price_change_warning_type",
        readonly=False,
    )

