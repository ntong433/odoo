# -*- coding: utf-8 -*-
import logging
from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Post-migration script to update Media category display name to XML-safe string."""
    _logger.info("Starting lhi_media_communications 19.0.2.1.0 post-migration...")
    env = api.Environment(cr, SUPERUSER_ID, {})

    xml_id = "lhi_media_communications.module_category_lhi_media"
    safe_name = "Media and Communications"
    category = env.ref(xml_id, raise_if_not_found=False)

    if category:
        old_name = category.name or ""
        if old_name != safe_name:
            _logger.info("Updating category %s display name from '%s' to '%s'", xml_id, old_name, safe_name)
            category.write({"name": safe_name})

    env.registry.clear_cache()
    _logger.info("Completed lhi_media_communications 19.0.2.1.0 post-migration.")
