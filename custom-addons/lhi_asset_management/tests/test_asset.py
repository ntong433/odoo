from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAssetRegister(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env["res.company"].create({"name": "Asset Test Company"})
        cls.state_ebonyi = cls.env["res.country.state"].create(
            {
                "name": "Ebonyi Test State",
                "code": "EB",
                "lhi_asset_code": "EBO",
                "country_id": cls.env.ref("base.ng").id,
            }
        )
        cls.state_bauchi = cls.env["res.country.state"].create(
            {
                "name": "Bauchi Test State",
                "code": "BC",
                "lhi_asset_code": "BAU",
                "country_id": cls.env.ref("base.ng").id,
            }
        )
        cls.office = cls.env["lhi.office"].create(
            {
                "name": "Asset Test Office",
                "code": "ATO",
                "company_id": cls.company.id,
            }
        )
        cls.project = cls.env["lhi.project"].create(
            {
                "name": "PLAN Test Project",
                "code": "PLAN",
                "office_id": cls.office.id,
                "company_id": cls.company.id,
            }
        )
        cls.category_furniture = cls.env["lhi.asset.category"].create(
            {
                "name": "Fixtures and Furniture",
                "code": "FF",
                "company_id": cls.company.id,
            }
        )
        cls.category_equipment = cls.env["lhi.asset.category"].create(
            {
                "name": "Office Equipment",
                "code": "OE",
                "company_id": cls.company.id,
            }
        )
        cls.condition = cls.env.ref("lhi_asset_management.asset_condition_good")
        cls.rule = cls.env["lhi.asset.tag.rule"].create(
            {
                "name": "Test Global Rule",
                "company_id": cls.company.id,
                "organisation_prefix": "LHI",
                "lhi_owner_code": "LHI",
                "sequence_strategy": "global",
                "padding": 4,
                "is_default": True,
            }
        )
        cls.partner_owner = cls.env["res.partner"].create(
            {"name": "Project Asset Legal Owner"}
        )
        cls.asset_officer = cls.env["res.users"].with_company(cls.company).create(
            {
                "name": "Asset Officer",
                "login": "asset-officer-test",
                "company_id": cls.company.id,
                "company_ids": [(6, 0, [cls.company.id])],
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref(
                                "lhi_security.group_lhi_asset_officer"
                            ).id
                        ],
                    )
                ],
                "lhi_office_ids": [(6, 0, [cls.office.id])],
                "lhi_project_ids": [(6, 0, [cls.project.id])],
            }
        )
        cls.asset_manager = cls.env["res.users"].with_company(cls.company).create(
            {
                "name": "Asset Manager",
                "login": "asset-manager-test",
                "company_id": cls.company.id,
                "company_ids": [(6, 0, [cls.company.id])],
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref(
                                "lhi_security.group_lhi_asset_manager"
                            ).id
                        ],
                    )
                ],
            }
        )
        cls.minimal_user = cls.env["res.users"].with_company(cls.company).create(
            {
                "name": "Minimal User",
                "login": "asset-minimal-test",
                "company_id": cls.company.id,
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )
        cls.env["lhi.approval.matrix"].create(
            {
                "name": "Asset Transfer Test Matrix",
                "document_type": "asset_transfer",
                "company_id": cls.company.id,
                "currency_id": cls.company.currency_id.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Asset Manager Approval",
                            "approver_group_id": cls.env.ref(
                                "lhi_security.group_lhi_asset_manager"
                            ).id,
                            "approver_ids": [(6, 0, [cls.asset_manager.id])],
                            "approval_type": "any",
                        },
                    )
                ],
            }
        )
        cls.env["lhi.approval.matrix"].create(
            {
                "name": "Asset Disposal Test Matrix",
                "document_type": "asset_disposal",
                "company_id": cls.company.id,
                "currency_id": cls.company.currency_id.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Asset Manager Approval",
                            "approver_group_id": cls.env.ref(
                                "lhi_security.group_lhi_asset_manager"
                            ).id,
                            "approver_ids": [(6, 0, [cls.asset_manager.id])],
                            "approval_type": "any",
                        },
                    )
                ],
            }
        )

    def _asset_values(self, **overrides):
        values = {
            "name": "Test Asset",
            "category_id": self.category_furniture.id,
            "condition_id": self.condition.id,
            "registration_state_id": self.state_ebonyi.id,
            "state_id": self.state_ebonyi.id,
            "legal_owner_id": self.company.partner_id.id,
            "currency_id": self.company.currency_id.id,
            "company_id": self.company.id,
        }
        values.update(overrides)
        return values

    def test_lhi_and_project_tags_use_atomic_global_sequence(self):
        first = self.env["lhi.asset"].with_user(self.asset_officer).create(
            self._asset_values(name="LHI Furniture")
        )
        first.action_confirm()
        self.assertEqual(first.asset_tag, "LHI/LHI/EBO/FF/0001")

        second = self.env["lhi.asset"].with_user(self.asset_officer).create(
            self._asset_values(
                name="PLAN Equipment",
                category_id=self.category_equipment.id,
                registration_state_id=self.state_bauchi.id,
                state_id=self.state_bauchi.id,
                legal_owner_id=self.partner_owner.id,
                project_id=self.project.id,
                project_abbreviation="PLAN",
            )
        )
        second.action_confirm()
        self.assertEqual(second.asset_tag, "LHI/PLAN/BAU/OE/0002")
        self.assertNotEqual(first.tag_sequence_number, second.tag_sequence_number)

    def test_confirmed_tag_is_immutable_and_state_transfer_preserves_it(self):
        asset = self.env["lhi.asset"].with_user(self.asset_officer).create(
            self._asset_values()
        )
        asset.action_confirm()
        original_tag = asset.asset_tag
        with self.assertRaises(ValidationError):
            asset.with_user(self.asset_officer).write({"asset_tag": "MANUAL"})

        transfer = self.env["lhi.asset.transfer"].with_user(
            self.asset_officer
        ).create(
            {
                "asset_id": asset.id,
                "transfer_type": "location",
                "dest_state_id": self.state_bauchi.id,
                "justification": "Move to Bauchi operational site",
            }
        )
        transfer.action_submit()
        with self.assertRaises(UserError):
            transfer.with_user(self.asset_officer).action_complete()
        transfer.approval_request_id.with_user(self.asset_manager).action_approve(
            notes="Approved move"
        )
        transfer.with_user(self.asset_officer).action_complete()
        self.assertEqual(asset.state_id, self.state_bauchi)
        self.assertEqual(asset.asset_tag, original_tag)
        self.assertTrue(asset.history_ids.filtered(lambda row: row.event_type == "movement"))

    def test_retag_requires_separate_asset_manager(self):
        asset = self.env["lhi.asset"].with_user(self.asset_officer).create(
            self._asset_values()
        )
        asset.action_confirm()
        old_tag = asset.asset_tag
        request = self.env["lhi.asset.retag.request"].with_user(
            self.asset_officer
        ).create(
            {
                "asset_id": asset.id,
                "reason": "Original label was physically damaged",
            }
        )
        request.action_submit()
        with self.assertRaises(AccessError):
            request.with_user(self.asset_officer).action_approve()
        request.with_user(self.asset_manager).action_approve()
        self.assertNotEqual(asset.asset_tag, old_tag)
        self.assertEqual(request.previous_tag, old_tag)
        self.assertEqual(request.new_tag, asset.asset_tag)

    def test_legacy_tag_is_preserved_and_classified(self):
        tag = "Old Register Number 17/A"
        asset = self.env["lhi.asset"].with_user(self.asset_officer).create(
            self._asset_values(asset_tag=tag)
        )
        asset.action_confirm()
        self.assertEqual(asset.asset_tag, tag)
        self.assertTrue(asset.legacy_tag)
        self.assertEqual(asset.tag_validation_status, "nonstandard")

    def test_history_is_immutable(self):
        asset = self.env["lhi.asset"].with_user(self.asset_officer).create(
            self._asset_values()
        )
        history = asset.history_ids[0]
        with self.assertRaises(AccessError):
            history.with_user(self.asset_manager).write({"description": "Changed"})
        with self.assertRaises(AccessError):
            history.with_user(self.asset_manager).unlink()

    def test_legacy_header_mapping_and_missing_tag_import(self):
        batch = self.env["lhi.asset.import.batch"].with_user(
            self.asset_officer
        ).create(
            {
                "source_filename": "legacy-assets.csv",
                "default_state_id": self.state_ebonyi.id,
                "company_id": self.company.id,
            }
        )
        self.assertEqual(
            batch._canonical_header("Type of Acquisition"), "acquisition_type"
        )
        self.assertEqual(batch._canonical_header("Purchase Vaue"), "asset_value")
        self.assertEqual(batch._canonical_header("cat_cal"), "category")
        self.assertEqual(batch._canonical_header("Asset SN"), "serial_number")
        self.assertEqual(batch._canonical_header("Asset Number"), "asset_tag")

        values = {
            "acquisition_type": "Purchased",
            "condition": "Good",
            "acquisition_date": "2026-07-01",
            "acquisition_source": "",
            "project_abbreviation": "",
            "asset_value": "12,500.50",
            "category": "FF",
            "serial_number": "IMPORT-SERIAL-1",
            "asset_tag": "",
            "asset_name": "Imported Table",
        }
        row = self.env["lhi.asset.import.row"].with_user(
            self.asset_officer
        ).create(batch._prepare_row_values(2, values, {"Other": "Kept"}, values))
        batch.action_validate()
        self.assertEqual(row.validation_state, "valid")
        batch.action_import()
        self.assertEqual(batch.state, "imported")
        self.assertTrue(row.asset_id.asset_tag.startswith("LHI/LHI/EBO/FF/"))
        self.assertEqual(row.asset_id.asset_value, 12500.50)
        self.assertIn("Other", row.extra_values_json)

    def test_import_duplicate_tag_is_an_explicit_error(self):
        existing = self.env["lhi.asset"].with_user(self.asset_officer).create(
            self._asset_values(asset_tag="LEGACY-EXACT-1")
        )
        existing.action_confirm()
        batch = self.env["lhi.asset.import.batch"].with_user(
            self.asset_officer
        ).create(
            {
                "source_filename": "duplicates.csv",
                "default_state_id": self.state_ebonyi.id,
                "company_id": self.company.id,
            }
        )
        values = {
            "acquisition_type": "Donated",
            "condition": "Good",
            "category": "FF",
            "asset_tag": "LEGACY-EXACT-1",
            "asset_name": "Duplicate Row",
        }
        row = self.env["lhi.asset.import.row"].with_user(
            self.asset_officer
        ).create(batch._prepare_row_values(2, values, {}, values))
        batch.action_validate()
        self.assertEqual(row.validation_state, "error")
        self.assertTrue(row.is_duplicate)
        self.assertIn("Duplicate Asset Number", row.error_message)

    def test_minimal_user_has_no_asset_access(self):
        with self.assertRaises(AccessError):
            self.env["lhi.asset"].with_user(self.minimal_user).check_access("read")
