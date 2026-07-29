# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Idempotently populate the operational fields introduced in 19.0.2."""
    cr.execute(
        """
        UPDATE lhi_asset
           SET asset_tag = NULL
         WHERE asset_tag LIKE '__LHI_UNTAGGED__%%'
        """
    )
    cr.execute(
        """
        UPDATE lhi_asset asset
           SET condition_id = condition.id
          FROM lhi_asset_condition condition
         WHERE asset.condition_id IS NULL
           AND condition.company_id IS NULL
           AND condition.code = CASE asset.condition
               WHEN 'new' THEN 'new'
               WHEN 'good' THEN 'good'
               WHEN 'fair' THEN 'fair'
               WHEN 'poor' THEN 'unserviceable'
               WHEN 'broken' THEN 'damaged'
               ELSE 'new'
           END
        """
    )
    cr.execute(
        """
        UPDATE lhi_asset asset
           SET legal_owner_id = company.partner_id
          FROM res_company company
         WHERE asset.company_id = company.id
           AND asset.legal_owner_id IS NULL
        """
    )
    cr.execute(
        """
        UPDATE lhi_asset asset
           SET currency_id = company.currency_id
          FROM res_company company
         WHERE asset.company_id = company.id
           AND asset.currency_id IS NULL
        """
    )
    cr.execute(
        """
        UPDATE lhi_asset
           SET registration_state_id = state_id
         WHERE registration_state_id IS NULL
           AND state_id IS NOT NULL
        """
    )
    cr.execute(
        """
        UPDATE lhi_asset
           SET legacy_tag = TRUE,
               tag_validation_status = CASE
                   WHEN asset_tag ~ '^[A-Z0-9][A-Z0-9-]*/[A-Z0-9][A-Z0-9-]*/[A-Z0-9][A-Z0-9-]*/[A-Z0-9][A-Z0-9-]*/[0-9]+$'
                   THEN 'valid'
                   ELSE 'nonstandard'
               END
         WHERE asset_tag IS NOT NULL
           AND (legacy_tag IS DISTINCT FROM TRUE
                OR tag_validation_status IS NULL
                OR tag_validation_status = 'unvalidated')
        """
    )

    env = api.Environment(cr, SUPERUSER_ID, {})
    rule_model = env["lhi.asset.tag.rule"]
    for company in env["res.company"].search([]):
        if not rule_model.search_count([("company_id", "=", company.id)]):
            rule_model.create(
                {
                    "name": "LHI Standard Asset Tag",
                    "company_id": company.id,
                    "organisation_prefix": "LHI",
                    "lhi_owner_code": "LHI",
                    "separator": "/",
                    "padding": 4,
                    "sequence_strategy": "global",
                    "is_default": True,
                }
            )

    for asset in env["lhi.asset"].search([]):
        if not asset.history_ids.filtered(
            lambda event: event.description
            == "Legacy asset migrated to the operational Asset Register."
        ):
            asset._lhi_add_history(
                "registration",
                "Legacy asset migrated to the operational Asset Register.",
            )
    _logger.info(
        "LHI Asset Register post-migration completed for %s assets",
        len(env["lhi.asset"].search([])),
    )
