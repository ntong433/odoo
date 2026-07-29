from odoo import Command
from odoo.tests.common import TransactionCase


class HubCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.hub_a = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        cls.hub_b = cls.env["stock.warehouse"].create(
            {"name": "Test Secondary HUB", "code": "TSH", "company_id": cls.company.id}
        )
        cls.category = cls.env.ref(
            "lhi_hub_management.product_category_lhi_consumables"
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "HUB Test Consumable",
                "is_storable": True,
                "tracking": "none",
                "categ_id": cls.category.id,
                "lhi_hub_item_type": "consumables",
                "lhi_value_source": "manual",
                "lhi_manual_value": 25.0,
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "HUB Test Recipient",
                "lhi_external_recipient": True,
                "lhi_recipient_type": "organization",
            }
        )
        cls.officer = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "HUB Test Operations Officer",
                    "login": "hub-test-operations-officer",
                    "email": "hub-operations@example.invalid",
                    "company_id": cls.company.id,
                    "company_ids": [Command.set(cls.company.ids)],
                    "group_ids": [
                        Command.set(
                            [
                                cls.env.ref("base.group_user").id,
                                cls.env.ref(
                                    "lhi_security.group_lhi_operations_officer"
                                ).id,
                            ]
                        )
                    ],
                    "lhi_hub_ids": [Command.set(cls.hub_a.ids)],
                }
            )
        )
        cls.manager = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "HUB Test Operations Manager",
                    "login": "hub-test-operations-manager",
                    "email": "hub-manager@example.invalid",
                    "company_id": cls.company.id,
                    "company_ids": [Command.set(cls.company.ids)],
                    "group_ids": [
                        Command.set(
                            [
                                cls.env.ref("base.group_user").id,
                                cls.env.ref(
                                    "lhi_security.group_lhi_operations_manager"
                                ).id,
                            ]
                        )
                    ],
                    "lhi_hub_ids": [Command.set(cls.hub_a.ids)],
                }
            )
        )
        cls.hub_a.write(
            {
                "lhi_operations_manager_id": cls.manager.id,
                "lhi_operations_officer_ids": [Command.set(cls.officer.ids)],
                "lhi_authorized_user_ids": [
                    Command.set((cls.officer | cls.manager).ids)
                ],
            }
        )
