# -*- coding: utf-8 -*-
from odoo import _, models


class LhiAsset(models.Model):
    _inherit = "lhi.asset"

    def action_assign(self):
        result = super().action_assign()
        for asset in self:
            self.env["lhi.hub.notification"].enqueue(
                source=asset,
                event_type="asset_assignment",
                message=_("Asset %(asset)s was assigned to %(custodian)s.")
                % {
                    "asset": asset.display_name,
                    "custodian": asset.custodian_id.display_name,
                },
                users=asset.custodian_id,
            )
        return result


class LhiAssetTransfer(models.Model):
    _inherit = "lhi.asset.transfer"

    def _lhi_asset_manager_users(self):
        group = self.env.ref("lhi_security.group_lhi_asset_manager")
        return self.env["res.users"].search(
            [
                ("active", "=", True),
                ("all_group_ids", "in", group.id),
                ("company_ids", "in", self.company_id.ids),
            ]
        )

    def action_complete(self):
        previous_custodians = {
            transfer.id: transfer.source_custodian_id for transfer in self
        }
        result = super().action_complete()
        manager_users = self._lhi_asset_manager_users()
        for transfer in self:
            disposal = transfer.transfer_type in ("write_off", "donation")
            recipients = (
                previous_custodians[transfer.id]
                | transfer.dest_custodian_id
                | manager_users.filtered(
                    lambda user: transfer.company_id in user.company_ids
                )
            )
            self.env["lhi.hub.notification"].enqueue(
                source=transfer,
                event_type="asset_disposal" if disposal else "asset_transfer",
                message=(
                    _("Asset disposal workflow %s was completed.")
                    if disposal
                    else _("Asset transfer workflow %s was completed.")
                )
                % transfer.name,
                users=recipients,
            )
        return result
