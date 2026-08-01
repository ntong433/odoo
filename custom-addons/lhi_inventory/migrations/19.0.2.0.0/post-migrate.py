# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Repair stock ACLs whose original XML IDs may be marked noupdate."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    viewer = env.ref("lhi_security.group_lhi_inventory_viewer")
    acl_values = {
        "stock.access_stock_warehouse_user": {},
        "stock.access_stock_location_all_user": {},
        "stock.access_stock_picking_type_all": {},
        "stock.access_stock_quant_all": {},
        "stock.access_stock_move_line_all": {
            "perm_read": True,
            "perm_write": False,
            "perm_create": False,
            "perm_unlink": False,
        },
    }
    changed = 0
    for xmlid, extra_values in acl_values.items():
        with cr.savepoint():
            acl = env.ref(xmlid, raise_if_not_found=False)
            if not acl:
                _logger.warning("Inventory RBAC migration could not resolve %s", xmlid)
                continue
            values = {"group_id": viewer.id, **extra_values}
            differs = any(
                (
                    acl[field_name].id
                    if field_name == "group_id"
                    else acl[field_name]
                )
                != value
                for field_name, value in values.items()
            )
            if differs:
                acl.write(values)
                changed += 1

    env.registry.clear_cache()
    _logger.info(
        "LHI Inventory RBAC migration repaired %s stock ACL records",
        changed,
    )
