from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import HubCommon


@tagged("post_install", "-at_install")
class TestHubOperations(HubCommon):
    def _issue(self, **extra):
        values = {
            "hub_id": self.hub_a.id,
            "recipient_id": self.partner.id,
            "issue_type": "free",
            "purpose": "Automated operational verification",
            "line_ids": [
                Command.create(
                    {
                        "product_id": self.product.id,
                        "uom_id": self.product.uom_id.id,
                        "quantity": 2,
                    }
                )
            ],
        }
        values.update(extra)
        return self.env["lhi.hub.external.issue"].create(values)

    def test_external_issue_blocks_negative_stock(self):
        issue = self._issue()
        with self.assertRaises(ValidationError):
            issue.with_user(self.officer).action_validate()
        self.assertEqual(issue.state, "draft")
        self.assertFalse(issue.picking_id)

    def test_external_issue_uses_validated_stock_move_and_revenue(self):
        self.env["stock.quant"]._update_available_quantity(
            self.product, self.hub_a.lot_stock_id, 3
        )
        method = self.env.ref("lhi_hub_management.payment_method_cash")
        issue = self._issue(
            issue_type="sale",
            amount_received=40,
            payment_method_id=method.id,
            line_ids=[
                Command.create(
                    {
                        "product_id": self.product.id,
                        "uom_id": self.product.uom_id.id,
                        "quantity": 2,
                        "unit_price": 20,
                    }
                )
            ],
        )
        issue.with_user(self.officer).action_validate()
        self.assertEqual(issue.state, "validated")
        self.assertEqual(issue.picking_id.state, "done")
        self.assertFalse("approval_request_id" in issue._fields)
        revenue = self.env["lhi.hub.operational.revenue"].search(
            [("source_model", "=", issue._name), ("source_id", "=", issue.id)]
        )
        self.assertEqual(revenue.amount, 40)

    def test_notification_deduplication(self):
        issue = self._issue()
        first = self.env["lhi.hub.notification"].enqueue(
            source=issue,
            event_type="test_event",
            message="Stable event",
            users=self.officer,
        )
        second = self.env["lhi.hub.notification"].enqueue(
            source=issue,
            event_type="test_event",
            message="Stable event",
            users=self.officer,
        )
        self.assertEqual(first, second)
        self.assertEqual(
            self.env["lhi.hub.notification"].search_count(
                [("deduplication_key", "=", first.deduplication_key)]
            ),
            1,
        )

    def test_low_stock_alert_is_queued_for_assigned_hub_staff(self):
        self.product.lhi_low_stock_threshold = 1
        self.env["lhi.hub.notification"]._cron_enqueue_stock_alerts()
        alerts = self.env["lhi.hub.notification"].search(
            [
                ("source_model", "=", self.product._name),
                ("source_id", "=", self.product.id),
                ("event_type", "=", "low_stock"),
            ]
        )
        self.assertEqual(
            set(alerts.mapped("recipient_id").ids),
            set((self.officer | self.manager).ids),
        )

    def test_stock_adjustment_requires_manager_reason_and_reverses(self):
        adjustment = (
            self.env["lhi.hub.stock.adjustment"]
            .with_user(self.manager)
            .create(
                {
                    "hub_id": self.hub_a.id,
                    "location_id": self.hub_a.lot_stock_id.id,
                    "reason": "Verified opening physical count",
                    "line_ids": [
                        Command.create(
                            {
                                "product_id": self.product.id,
                                "uom_id": self.product.uom_id.id,
                                "adjustment_quantity": 4,
                            }
                        )
                    ],
                }
            )
        )
        adjustment.with_user(self.manager).action_validate()
        self.assertEqual(adjustment.state, "validated")
        self.assertEqual(adjustment.line_ids.quantity_before, 0)
        self.assertEqual(adjustment.line_ids.quantity_after, 4)
        self.assertTrue(adjustment.line_ids.move_id.is_inventory)

        adjustment.with_user(self.manager).reversal_reason = "Opening count corrected"
        adjustment.with_user(self.manager).action_reverse()
        self.assertEqual(adjustment.state, "reversed")
        self.assertEqual(adjustment.reversal_id.state, "validated")

    def test_pharmaceutical_requires_tracking_and_expiry(self):
        with self.assertRaises(ValidationError):
            self.env["product.product"].create(
                {
                    "name": "Unsafe Medicine",
                    "is_storable": True,
                    "tracking": "none",
                    "lhi_hub_item_type": "pharmaceuticals",
                }
            )
