from datetime import datetime

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPurchasePriceChangeWarning(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({
            "purchase_price_change_warning_enabled": True,
            "purchase_price_change_warning_threshold": 10.0,
            "purchase_price_change_warning_type": "increase",
        })
        cls.vendor = cls.env["res.partner"].create({"name": "Test Vendor A"})
        cls.other_vendor = cls.env["res.partner"].create({"name": "Test Vendor B"})
        cls.vendor_contact = cls.env["res.partner"].create({
            "name": "Vendor A Purchasing Contact",
            "parent_id": cls.vendor.id,
        })
        cls.unit = cls.env.ref("uom.product_uom_unit")
        cls.pack = cls.env.ref("uom.product_uom_pack_6")
        cls.product = cls.env["product.product"].create({
            "name": "Price Warning Test Product",
            "purchase_ok": True,
            "uom_id": cls.unit.id,
            "uom_ids": [(6, 0, [cls.pack.id])],
        })
        cls.other_product = cls.env["product.product"].create({
            "name": "Other Price Warning Product",
            "purchase_ok": True,
            "uom_id": cls.unit.id,
        })

    def _create_order_line(
        self,
        price,
        *,
        vendor=None,
        product=None,
        state="draft",
        currency=None,
        uom=None,
        quantity=1.0,
        order_date="2026-01-15 10:00:00",
        approval_date=None,
    ):
        order = self.env["purchase.order"].create({
            "partner_id": (vendor or self.vendor).id,
            "company_id": self.company.id,
            "currency_id": (currency or self.company.currency_id).id,
            "date_order": order_date,
            "date_approve": approval_date or (order_date if state == "purchase" else False),
            "state": state,
        })
        return self.env["purchase.order.line"].create({
            "order_id": order.id,
            "product_id": (product or self.product).id,
            "product_qty": quantity,
            "uom_id": (uom or self.unit).id,
            "price_unit": price,
            "date_planned": datetime(2026, 2, 1, 10, 0, 0),
        })

    def test_same_commercial_vendor_and_product_uses_latest_price(self):
        old = self._create_order_line(8.0, order_date="2026-01-01 10:00:00", state="purchase")
        latest = self._create_order_line(
            10.0,
            vendor=self.vendor_contact,
            order_date="2026-01-10 10:00:00",
            state="purchase",
        )
        current = self._create_order_line(12.0)

        self.assertEqual(current.previous_purchase_order_id, latest.order_id)
        self.assertNotEqual(current.previous_purchase_order_id, old.order_id)
        self.assertAlmostEqual(current.previous_purchase_price, 10.0)
        self.assertAlmostEqual(current.price_change_percentage, 20.0)
        self.assertEqual(current.price_change_display, "+20.00%")
        self.assertEqual(current.previous_purchase_quantity, latest.product_qty)
        self.assertEqual(current.previous_purchase_uom_id, latest.uom_id)
        self.assertEqual(current.previous_purchase_currency_id, latest.currency_id)

    def test_different_vendor_and_product_are_ignored(self):
        self._create_order_line(4.0, vendor=self.other_vendor, state="purchase")
        self._create_order_line(5.0, product=self.other_product, state="purchase")
        current = self._create_order_line(12.0)

        self.assertFalse(current.previous_purchase_order_id)
        self.assertFalse(current.purchase_price_change_warning)

    def test_other_company_history_is_ignored(self):
        other_company = self.env["res.company"].create({
            "name": "Other Price Warning Company",
            "currency_id": self.company.currency_id.id,
        })
        order = self.env["purchase.order"].create({
            "partner_id": self.vendor.id,
            "company_id": other_company.id,
            "currency_id": other_company.currency_id.id,
            "date_order": "2026-01-10 10:00:00",
            "date_approve": "2026-01-10 10:00:00",
            "state": "purchase",
        })
        self.env["purchase.order.line"].create({
            "order_id": order.id,
            "product_id": self.product.id,
            "product_qty": 1.0,
            "uom_id": self.unit.id,
            "price_unit": 10.0,
            "date_planned": datetime(2026, 2, 1, 10, 0, 0),
        })
        current = self._create_order_line(12.0)

        self.assertFalse(current.previous_purchase_order_id)

    def test_purchase_user_reads_comparison_through_standard_access(self):
        purchase_user = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Price Warning Purchase User",
            "login": "price-warning-purchase-user",
            "company_id": self.company.id,
            "company_ids": [(6, 0, [self.company.id])],
            "group_ids": [(6, 0, [self.env.ref("purchase.group_purchase_user").id])],
        })
        previous = self._create_order_line(10.0, state="purchase")
        current = self._create_order_line(12.0)

        purchase_user_line = current.with_user(purchase_user)
        self.assertEqual(purchase_user_line.previous_purchase_order_id, previous.order_id)
        self.assertAlmostEqual(purchase_user_line.price_change_percentage, 20.0)

    def test_no_history_produces_blank_comparison_and_no_warning(self):
        current = self._create_order_line(12.0)

        self.assertFalse(current.previous_purchase_order_id)
        self.assertFalse(current.previous_purchase_price)
        self.assertFalse(current.price_change_display)
        self.assertFalse(current.purchase_price_change_warning)

    def test_unconfirmed_cancelled_and_zero_history_are_ignored(self):
        self._create_order_line(7.0, state="draft")
        self._create_order_line(7.5, state="sent")
        self._create_order_line(7.75, state="to approve")
        self._create_order_line(8.0, state="cancel")
        self._create_order_line(0.0, state="purchase")
        current = self._create_order_line(12.0)

        self.assertFalse(current.previous_purchase_order_id)
        self.assertFalse(current.price_change_display)

    def test_signed_change_threshold_and_warning_modes(self):
        self._create_order_line(100.0, state="purchase")
        at_boundary = self._create_order_line(110.0)
        below_boundary = self._create_order_line(109.99)
        decrease = self._create_order_line(85.0)

        self.assertTrue(at_boundary.purchase_price_change_warning)
        self.assertEqual(at_boundary.purchase_price_change_warning_icon, "⚠")
        self.assertFalse(below_boundary.purchase_price_change_warning)
        self.assertAlmostEqual(decrease.price_change_percentage, -15.0)
        self.assertEqual(decrease.price_change_display, "-15.00%")
        self.assertFalse(decrease.purchase_price_change_warning)

        self.company.purchase_price_change_warning_type = "both"
        self.assertTrue(decrease.purchase_price_change_warning)

    def test_disabled_setting_blanks_comparison_and_warning(self):
        self._create_order_line(10.0, state="purchase")
        current = self._create_order_line(20.0)
        self.company.purchase_price_change_warning_enabled = False

        self.assertFalse(current.previous_purchase_price)
        self.assertFalse(current.price_change_display)
        self.assertFalse(current.purchase_price_change_warning)

    def test_uom_conversion_normalizes_unit_price(self):
        self._create_order_line(60.0, state="purchase", uom=self.pack)
        current = self._create_order_line(10.0, uom=self.unit)

        self.assertAlmostEqual(current.previous_purchase_price, 10.0)
        self.assertAlmostEqual(current.price_change_percentage, 0.0)
        self.assertFalse(current.purchase_price_change_warning)

    def test_currency_conversion_uses_historical_confirmation_date(self):
        source = self.env["res.currency"].create({
            "name": "XPC",
            "symbol": "X",
            "rounding": 0.01,
        })
        target = self.env["res.currency"].create({
            "name": "YPC",
            "symbol": "Y",
            "rounding": 0.01,
        })
        self.env["res.currency.rate"].create([
            {"currency_id": source.id, "name": "2026-01-01", "rate": 2.0, "company_id": self.company.id},
            {"currency_id": source.id, "name": "2026-02-01", "rate": 4.0, "company_id": self.company.id},
            {"currency_id": target.id, "name": "2026-01-01", "rate": 1.0, "company_id": self.company.id},
        ])
        self._create_order_line(
            100.0,
            state="purchase",
            currency=source,
            order_date="2026-01-15 10:00:00",
        )
        current = self._create_order_line(
            50.0,
            currency=target,
            order_date="2026-03-01 10:00:00",
        )

        self.assertAlmostEqual(current.previous_purchase_price, 50.0)
        self.assertAlmostEqual(current.price_change_percentage, 0.0)

    def test_manual_price_change_recomputes_percentage_and_warning(self):
        self._create_order_line(100.0, state="purchase")
        current = self._create_order_line(105.0)
        self.assertFalse(current.purchase_price_change_warning)

        current.price_unit = 125.0

        self.assertAlmostEqual(current.price_change_percentage, 25.0)
        self.assertTrue(current.purchase_price_change_warning)
        self.assertIn("+25.00%", str(current.purchase_price_change_warning_message))

    def test_warning_does_not_block_purchase_confirmation(self):
        self._create_order_line(100.0, state="purchase")
        current = self._create_order_line(125.0)
        self.assertTrue(current.purchase_price_change_warning)

        current.order_id.button_confirm()

        self.assertEqual(current.order_id.state, "purchase")

    def test_warning_message_escapes_historical_order_reference(self):
        previous = self._create_order_line(100.0, state="purchase")
        previous.order_id.name = "<script>alert('price')</script>"
        current = self._create_order_line(125.0)

        message = str(current.purchase_price_change_warning_message)
        self.assertNotIn("<script>", message)
        self.assertIn("&lt;script&gt;", message)

    def test_deterministic_tie_break_uses_latest_line_id(self):
        first = self._create_order_line(10.0, state="purchase")
        second = self._create_order_line(20.0, state="purchase")
        current = self._create_order_line(30.0)

        self.assertGreater(second.id, first.id)
        self.assertEqual(current.previous_purchase_order_id, second.order_id)
        self.assertAlmostEqual(current.previous_purchase_price, 20.0)

    def test_latest_duplicate_product_line_in_order_is_used(self):
        first = self._create_order_line(10.0, state="purchase")
        latest_line = self.env["purchase.order.line"].create({
            "order_id": first.order_id.id,
            "product_id": self.product.id,
            "product_qty": 1.0,
            "uom_id": self.unit.id,
            "price_unit": 15.0,
            "date_planned": datetime(2026, 2, 1, 10, 0, 0),
        })
        current = self._create_order_line(18.0)

        self.assertGreater(latest_line.id, first.id)
        self.assertEqual(current.previous_purchase_order_id, first.order_id)
        self.assertAlmostEqual(current.previous_purchase_price, 15.0)
