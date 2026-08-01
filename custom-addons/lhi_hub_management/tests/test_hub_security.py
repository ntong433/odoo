from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import HubCommon
from ..models.hub_structure import LHI_HUB_SYSTEM_TOKEN


@tagged("post_install", "-at_install")
class TestHubSecurity(HubCommon):
    def test_assigned_hub_record_rule(self):
        visible = self.env["stock.warehouse"].with_user(self.officer).search([])
        self.assertIn(self.hub_a, visible)
        self.assertNotIn(self.hub_b, visible)

    def test_auditor_cannot_execute_hub_workflow(self):
        auditor = (
            self.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "HUB Read-only Auditor",
                    "login": "hub-test-auditor",
                    "company_id": self.company.id,
                    "company_ids": [Command.set(self.company.ids)],
                    "group_ids": [
                        Command.set(
                            [
                                self.env.ref("base.group_user").id,
                                self.env.ref(
                                    "lhi_security.group_lhi_system_auditor"
                                ).id,
                            ]
                        )
                    ],
                }
            )
        )
        issue = self.env["lhi.hub.external.issue"].create(
            {
                "hub_id": self.hub_a.id,
                "recipient_id": self.partner.id,
                "purpose": "Auditor denial test",
                "line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "uom_id": self.product.uom_id.id,
                            "quantity": 1,
                        }
                    )
                ],
            }
        )
        with self.assertRaises(AccessError):
            issue.with_user(auditor).action_validate()

    def test_hub_approval_snapshot_is_immutable(self):
        with self.assertRaises(AccessError):
            self.env["lhi.approval.request"].with_context(
                lhi_hub_approval_system=True
            ).create(
                {
                    "res_model": "lhi.hub.stock.request",
                    "res_id": 999999,
                    "document_type": "hub_stock_request",
                    "amount": 0,
                    "currency_id": self.company.currency_id.id,
                    "creator_id": self.officer.id,
                    "company_id": self.company.id,
                }
            )
        approval = (
            self.env["lhi.approval.request"]
            .with_context(lhi_hub_approval_system=LHI_HUB_SYSTEM_TOKEN)
            .create(
                {
                    "res_model": "lhi.hub.stock.request",
                    "res_id": 999999,
                    "document_type": "hub_stock_request",
                    "amount": 0,
                    "currency_id": self.company.currency_id.id,
                    "creator_id": self.officer.id,
                    "company_id": self.company.id,
                }
            )
        )
        line = (
            self.env["lhi.approval.request.line"]
            .sudo()
            .with_context(lhi_hub_approval_system=LHI_HUB_SYSTEM_TOKEN)
            .create(
                {
                    "request_id": approval.id,
                    "name": "Snapshot",
                    "sequence": 10,
                    "approver_group_id": self.env.ref(
                        "lhi_security.group_lhi_hub_manager"
                    ).id,
                    "approver_ids": [Command.set(self.manager.ids)],
                    "approval_type": "any",
                    "state": "pending",
                }
            )
        )
        with self.assertRaises(AccessError):
            line.write({"approver_ids": [Command.clear()]})
        with self.assertRaises(AccessError):
            approval.action_approve()
