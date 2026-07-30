# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError


class TestAssetImportReconciliation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.sokoto_state = cls.env["res.country.state"].search(
            [("code", "=", "NG-SO")], limit=1
        )
        if not cls.sokoto_state:
            cls.sokoto_state = cls.env["res.country.state"].create({
                "name": "Sokoto",
                "code": "NG-SO",
                "country_id": cls.env.ref("base.ng").id,
                "lhi_asset_code": "SOK",
            })
        elif not cls.sokoto_state.lhi_asset_code:
            cls.sokoto_state.write({"lhi_asset_code": "SOK"})

        cls.condition = cls.env["lhi.asset.condition"].search([], limit=1)
        if not cls.condition:
            cls.condition = cls.env["lhi.asset.condition"].create({
                "name": "Good",
                "code": "GOOD",
            })

        cls.batch = cls.env["lhi.asset.import.batch"].create({
            "source_filename": "sokoto_legacy_register.xlsx",
            "default_state_id": cls.sokoto_state.id,
            "company_id": cls.company.id,
        })

    def test_01_category_reconciliation_deduplication(self):
        """Verify multiple rows with category code FF create only one category."""
        rows_data = [
            {
                "batch_id": self.batch.id,
                "row_number": 2,
                "asset_name": "Office Desk 1",
                "category_text": "FF",
                "condition_text": "GOOD",
                "state_text": "SOK",
            },
            {
                "batch_id": self.batch.id,
                "row_number": 3,
                "asset_name": "Office Chair 2",
                "category_text": "FF",
                "condition_text": "GOOD",
                "state_text": "SOK",
            },
        ]
        self.env["lhi.asset.import.row"].create(rows_data)
        self.batch.action_validate()

        categories = self.env["lhi.asset.category"].search([("code", "=", "FF")])
        self.assertEqual(len(categories), 1, "Only one FF category should be created.")
        self.assertEqual(self.batch.created_category_count, 1)

    def test_02_project_code_reconciliation_deduplication(self):
        """Verify multiple rows with project code LHI create only one project record."""
        rows_data = [
            {
                "batch_id": self.batch.id,
                "row_number": 4,
                "asset_name": "Project Laptop 1",
                "category_text": "OE",
                "project_abbreviation": "LHI",
                "condition_text": "GOOD",
                "state_text": "SOK",
            },
            {
                "batch_id": self.batch.id,
                "row_number": 5,
                "asset_name": "Project Printer 2",
                "category_text": "OE",
                "project_abbreviation": "LHI",
                "condition_text": "GOOD",
                "state_text": "SOK",
            },
        ]
        self.env["lhi.asset.import.row"].create(rows_data)
        self.batch.action_validate()

        projects = self.env["lhi.project"].search([("code", "=", "LHI")])
        self.assertEqual(len(projects), 1, "Only one LHI project should be created.")
        self.assertEqual(self.batch.created_project_count, 1)

    def test_03_vendor_reconciliation_capitalization_deduplication(self):
        """Verify repeated vendor names with different capitalization resolve to one partner."""
        rows_data = [
            {
                "batch_id": self.batch.id,
                "row_number": 6,
                "asset_name": "Purchased Item A",
                "category_text": "OE",
                "acquisition_source_text": "DIVINE FREEDOM TRADING COMPANY",
                "condition_text": "GOOD",
                "state_text": "SOK",
            },
            {
                "batch_id": self.batch.id,
                "row_number": 7,
                "asset_name": "Purchased Item B",
                "category_text": "OE",
                "acquisition_source_text": "Divine Freedom Trading Company",
                "condition_text": "GOOD",
                "state_text": "SOK",
            },
            {
                "batch_id": self.batch.id,
                "row_number": 8,
                "asset_name": "Purchased Item C",
                "category_text": "OE",
                "acquisition_source_text": "divine freedom trading company",
                "condition_text": "GOOD",
                "state_text": "SOK",
            },
        ]
        self.env["lhi.asset.import.row"].create(rows_data)
        self.batch.action_validate()

        partners = self.env["res.partner"].search([("name", "=ilike", "DIVINE FREEDOM TRADING COMPANY")])
        self.assertEqual(len(partners), 1, "Capitalization variants should resolve to exactly one partner.")
        self.assertEqual(self.batch.created_partner_count, 1)

    def test_04_master_data_reconciliation_idempotency(self):
        """Verify revalidating the batch creates no duplicate master records."""
        self.env["lhi.asset.import.row"].create({
            "batch_id": self.batch.id,
            "row_number": 9,
            "asset_name": "Idempotent Test Item",
            "category_text": "IDEM",
            "project_abbreviation": "IDEMPROJ",
            "acquisition_source_text": "Idem Vendor",
            "condition_text": "GOOD",
            "state_text": "SOK",
        })
        self.batch.action_validate()

        cat_count_before = self.env["lhi.asset.category"].search_count([("code", "=", "IDEM")])
        proj_count_before = self.env["lhi.project"].search_count([("code", "=", "IDEMPROJ")])

        # Return to draft and revalidate
        self.batch.action_return_to_draft()
        self.batch.action_validate()

        cat_count_after = self.env["lhi.asset.category"].search_count([("code", "=", "IDEM")])
        proj_count_after = self.env["lhi.project"].search_count([("code", "=", "IDEMPROJ")])

        self.assertEqual(cat_count_before, cat_count_after, "Revalidating must not duplicate categories.")
        self.assertEqual(proj_count_before, proj_count_after, "Revalidating must not duplicate projects.")

    def test_05_serial_number_duplicate_handling(self):
        """Verify blank serials are ignored, but repeated non-empty serials are flagged as duplicates."""
        rows_data = [
            {
                "batch_id": self.batch.id,
                "row_number": 10,
                "asset_name": "Item Blank Serial 1",
                "serial_number": "",
                "category_text": "OE",
                "condition_text": "GOOD",
                "state_text": "SOK",
            },
            {
                "batch_id": self.batch.id,
                "row_number": 11,
                "asset_name": "Item Blank Serial 2",
                "serial_number": False,
                "category_text": "OE",
                "condition_text": "GOOD",
                "state_text": "SOK",
            },
            {
                "batch_id": self.batch.id,
                "row_number": 12,
                "asset_name": "Item Serial ABC 1",
                "serial_number": "SN-999-XYZ",
                "category_text": "OE",
                "condition_text": "GOOD",
                "state_text": "SOK",
            },
            {
                "batch_id": self.batch.id,
                "row_number": 13,
                "asset_name": "Item Serial ABC 2",
                "serial_number": "SN-999-XYZ ",
                "category_text": "OE",
                "condition_text": "GOOD",
                "state_text": "SOK",
            },
        ]
        rows = self.env["lhi.asset.import.row"].create(rows_data)
        self.batch.action_validate()

        # Row 10 and 11 should be valid (blank serials not duplicate)
        self.assertEqual(rows[0].validation_state, "valid")
        self.assertEqual(rows[1].validation_state, "valid")

        # Row 12 should be valid (first occurrence)
        self.assertEqual(rows[2].validation_state, "valid")

        # Row 13 should be error & duplicate (second occurrence)
        self.assertEqual(rows[3].validation_state, "error")
        self.assertTrue(rows[3].is_duplicate)
        self.assertIn("First occurrence: row 12", rows[3].error_message)

    def test_06_asset_tag_whitespace_separator_normalization(self):
        """Verify asset tags differing only by accidental whitespace are detected as duplicates."""
        rows_data = [
            {
                "batch_id": self.batch.id,
                "row_number": 14,
                "asset_name": "Tag Test Item 1",
                "asset_tag": "LHI/LHI/SOK/FF/0020",
                "category_text": "FF",
                "condition_text": "GOOD",
                "state_text": "SOK",
            },
            {
                "batch_id": self.batch.id,
                "row_number": 15,
                "asset_name": "Tag Test Item 2",
                "asset_tag": "LHI/LHI /SOK/FF/0020",
                "category_text": "FF",
                "condition_text": "GOOD",
                "state_text": "SOK",
            },
        ]
        rows = self.env["lhi.asset.import.row"].create(rows_data)
        self.batch.action_validate()

        self.assertEqual(rows[0].validation_state, "valid")
        self.assertEqual(rows[1].validation_state, "error")
        self.assertTrue(rows[1].is_duplicate)
        self.assertIn("First occurrence: row 14", rows[1].error_message)

    def test_07_sokoto_state_resolution(self):
        """Verify Sokoto resolves to res.country.state code NG-SO."""
        row = self.env["lhi.asset.import.row"].create({
            "batch_id": self.batch.id,
            "row_number": 16,
            "asset_name": "Sokoto Asset Item",
            "category_text": "FF",
            "condition_text": "GOOD",
            "state_text": "SOK",
        })
        self.batch.action_validate()

        self.assertEqual(row.registration_state_id, self.sokoto_state)
        self.assertEqual(row.registration_state_id.code, "NG-SO")
