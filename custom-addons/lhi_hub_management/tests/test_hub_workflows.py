from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from .common import HubCommon
from ..models.hub_structure import LHI_HUB_SYSTEM_TOKEN


@tagged("post_install", "-at_install")
class TestHubWorkflows(HubCommon):
    def test_matrix_matches_requested_value_before_quantity_review(self):
        matrix = self.env["lhi.approval.matrix"].create(
            {
                "name": "Requested value route",
                "document_type": "hub_stock_request",
                "min_amount": 40,
                "max_amount": 60,
                "currency_id": self.company.currency_id.id,
                "company_id": self.company.id,
                "lhi_requesting_hub_ids": [Command.set(self.hub_a.ids)],
                "lhi_supplying_hub_ids": [Command.set(self.hub_b.ids)],
                "lhi_product_ids": [Command.set(self.product.ids)],
                "lhi_min_quantity": 2,
                "lhi_max_quantity": 2,
            }
        )
        request = self.env["lhi.hub.stock.request"].create(
            {
                "requesting_hub_id": self.hub_a.id,
                "supplying_hub_id": self.hub_b.id,
                "approval_matrix_id": matrix.id,
                "purpose": "Requested-value route verification",
                "line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "item_description": self.product.display_name,
                            "uom_id": self.product.uom_id.id,
                            "quantity_requested": 2,
                            "quantity_approved": 0,
                            "operational_unit_value": 25,
                            "purpose_remarks": "Test",
                        }
                    )
                ],
            }
        )
        self.assertEqual(request.requested_operational_value, 50)
        self.assertEqual(request.total_operational_value, 0)
        self.assertTrue(matrix._lhi_matches_hub_request(request))

    def test_active_serial_cannot_be_double_leased(self):
        product = self.env["product.product"].create(
            {
                "name": "Leaseable Serial Equipment",
                "is_storable": True,
                "tracking": "serial",
                "lhi_hub_item_type": "medical",
                "lhi_leaseable": True,
            }
        )
        lot = self.env["stock.lot"].create(
            {
                "name": "LEASE-SERIAL-001",
                "product_id": product.id,
                "company_id": self.company.id,
            }
        )
        active = self.env["lhi.hub.equipment.lease"].create(
            {
                "hub_id": self.hub_a.id,
                "lessee_id": self.partner.id,
                "expected_return_date": "2099-01-31",
                "purpose": "First lease",
                "line_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "lot_id": lot.id,
                            "agreed_amount": 10,
                        }
                    )
                ],
            }
        )
        active.with_context(lhi_hub_lease_system=LHI_HUB_SYSTEM_TOKEN).write(
            {"state": "active"}
        )
        second = self.env["lhi.hub.equipment.lease"].create(
            {
                "hub_id": self.hub_a.id,
                "lessee_id": self.partner.id,
                "expected_return_date": "2099-02-28",
                "purpose": "Conflicting lease",
                "line_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "lot_id": lot.id,
                            "agreed_amount": 10,
                        }
                    )
                ],
            }
        )
        with self.assertRaises(ValidationError):
            second.line_ids._lhi_validate_release()

    def test_posted_payment_is_immutable_and_reversal_required(self):
        lease = self.env["lhi.hub.equipment.lease"].create(
            {
                "hub_id": self.hub_a.id,
                "lessee_id": self.partner.id,
                "expected_return_date": "2099-01-31",
                "purpose": "Payment test",
            }
        )
        payment = self.env["lhi.hub.lease.payment"].create(
            {
                "lease_id": lease.id,
                "amount": 50,
                "payment_method_id": self.env.ref(
                    "lhi_hub_management.payment_method_cash"
                ).id,
            }
        )
        payment.with_user(self.officer).action_post()
        with self.assertRaises(AccessError):
            payment.write({"amount": 60})
        payment.with_user(
            self.manager
        ).reversal_reason = "Duplicate collection corrected"
        payment.with_user(self.manager).action_reverse()
        self.assertEqual(payment.state, "reversed")
        self.assertEqual(
            sum(
                self.env["lhi.hub.operational.revenue"]
                .search(
                    [
                        ("source_model", "=", payment._name),
                        ("source_id", "=", payment.id),
                    ]
                )
                .mapped("amount")
            ),
            0,
        )
