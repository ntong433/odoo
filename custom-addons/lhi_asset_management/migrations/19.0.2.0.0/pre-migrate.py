# -*- coding: utf-8 -*-
import logging


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Stop on identifier conflicts before unique constraints are installed."""
    cr.execute(
        """
        SELECT asset_tag, array_agg(id ORDER BY id)
          FROM lhi_asset
         WHERE asset_tag IS NOT NULL
           AND btrim(asset_tag) <> ''
           AND asset_tag NOT IN ('New', '/')
         GROUP BY asset_tag
        HAVING count(*) > 1
         ORDER BY asset_tag
         LIMIT 20
        """
    )
    duplicate_tags = cr.fetchall()
    if duplicate_tags:
        raise RuntimeError(
            "Unsafe Asset Register upgrade: duplicate legacy asset tags exist: %s"
            % duplicate_tags
        )

    cr.execute(
        """
        SELECT company_id, serial_number, array_agg(id ORDER BY id)
          FROM lhi_asset
         WHERE serial_number IS NOT NULL
           AND btrim(serial_number) <> ''
         GROUP BY company_id, serial_number
        HAVING count(*) > 1
         ORDER BY company_id, serial_number
         LIMIT 20
        """
    )
    duplicate_serials = cr.fetchall()
    if duplicate_serials:
        raise RuntimeError(
            "Unsafe Asset Register upgrade: duplicate manufacturer serial "
            "numbers exist within a company: %s" % duplicate_serials
        )

    cr.execute(
        """
        SELECT id, code
          FROM lhi_asset_category
         WHERE code IS NULL
            OR btrim(code) = ''
            OR upper(btrim(code)) !~ '^[A-Z0-9][A-Z0-9-]*$'
         ORDER BY id
         LIMIT 20
        """
    )
    invalid_categories = cr.fetchall()
    if invalid_categories:
        raise RuntimeError(
            "Unsafe Asset Register upgrade: category codes must be populated "
            "and contain only letters, numbers, or hyphens: %s"
            % invalid_categories
        )

    # "New" and "/" were technical placeholders in the old addon, not issued
    # business identifiers. Make them temporarily unique so the schema upgrade
    # can install the tag constraint; post-migration converts them to untagged.
    cr.execute(
        """
        UPDATE lhi_asset
           SET asset_tag = '__LHI_UNTAGGED__' || id
         WHERE asset_tag IN ('New', '/')
            OR btrim(asset_tag) = ''
        """
    )
    cr.execute(
        """
        UPDATE lhi_asset
           SET state = CASE state
               WHEN 'active' THEN 'in_use'
               WHEN 'maintenance' THEN 'under_repair'
               WHEN 'transfer' THEN 'in_transit'
               ELSE state
           END
         WHERE state IN ('active', 'maintenance', 'transfer')
        """
    )
    _logger.info("LHI Asset Register pre-migration safety checks passed")
