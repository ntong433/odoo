from odoo import api, SUPERUSER_ID
from odoo.addons.lhi_hub_management.models.hub_structure import (
    LHI_HUB_SYSTEM_TOKEN,
)


def migrate(cr, version):
    """Classify existing storable products under protected HUB categories.

    No stock quantities, approval state, accounting data, document bytes, or
    user authorization are changed by this migration.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    categories = env["product.category"].search(
        [("lhi_hub_category_code", "!=", False)]
    )
    for category in categories:
        templates = env["product.template"].search(
            [
                ("categ_id", "child_of", category.id),
                ("is_storable", "=", True),
                ("lhi_hub_item_type", "=", False),
            ]
        )
        templates.write({"lhi_hub_item_type": category.lhi_hub_category_code})
    lots = env["stock.lot"].search([("lhi_hub_id", "=", False)])
    for lot in lots:
        hub = lot.location_id.warehouse_id
        if hub:
            lot.with_context(lhi_hub_stock_system=LHI_HUB_SYSTEM_TOKEN).write(
                {"lhi_hub_id": hub.id}
            )
