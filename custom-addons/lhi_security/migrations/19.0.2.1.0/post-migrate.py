# -*- coding: utf-8 -*-
import logging
from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

SAFE_CATEGORY_NAMES = {
    "lhi_security.module_category_lhi_operations": "LHI Operations and HUB",
    "lhi_security.module_category_lhi_programmes": "LHI Programmes and Projects",
    "lhi_media_communications.module_category_lhi_media": "Media and Communications",
}


def migrate(cr, version):
    """Post-migration script to update ir.module.category display names to XML-safe strings."""
    _logger.info("Starting lhi_security 19.0.2.1.0 post-migration XML-safe category label update...")
    env = api.Environment(cr, SUPERUSER_ID, {})

    updated_count = 0
    for xml_id, safe_name in SAFE_CATEGORY_NAMES.items():
        category = env.ref(xml_id, raise_if_not_found=False)
        if not category:
            _logger.info("Category %s not found (may not be installed). Skipping.", xml_id)
            continue

        old_name = category.name or ""
        if old_name != safe_name:
            _logger.info("Updating category %s display name from '%s' to '%s'", xml_id, old_name, safe_name)
            category.write({"name": safe_name})
            updated_count += 1
        else:
            _logger.info("Category %s display name is already safe ('%s').", xml_id, safe_name)

    # Invalidate translations that might match old unsafe names
    if updated_count > 0:
        cr.execute("""
            UPDATE ir_translation
            SET src = REPLACE(src, '&', 'and'), value = REPLACE(value, '&', 'and')
            WHERE type = 'model' AND name = 'ir.module.category,name' AND (src LIKE '%&%' OR value LIKE '%&%')
        """)

    env.registry.clear_cache()
    _logger.info("Completed lhi_security 19.0.2.1.0 post-migration. Updated %d category label(s).", updated_count)
