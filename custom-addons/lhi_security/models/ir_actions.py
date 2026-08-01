# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import AccessError

from .res_users import LHI_APP_SELECTION


class IrActionsActions(models.Model):
    _inherit = "ir.actions.actions"

    lhi_app_key = fields.Selection(
        selection=LHI_APP_SELECTION,
        string="LHI Application",
        index=True,
        help=(
            "Authoritative LHI application entitlement required to load this "
            "action directly. If omitted, tagged menu ancestors are inspected."
        ),
    )

    def _lhi_action_app_keys(self):
        """Resolve explicit or menu-inherited app keys without leaking menus."""
        self.ensure_one()
        action = self.sudo()
        if action.lhi_app_key:
            return {action.lhi_app_key}

        menus = self.env["ir.ui.menu"].sudo().with_context(active_test=True).search(
            [
                ("action", "=", f"{self._name},{self.id}"),
                ("active", "=", True),
            ]
        )
        app_keys = set()
        for menu in menus:
            current = menu
            while current:
                if not current.active:
                    break
                if current.lhi_app_key:
                    app_keys.add(current.lhi_app_key)
                    break
                current = current.parent_id
        return app_keys

    def _get_action_dict(self):
        self.ensure_one()
        app_keys = self._lhi_action_app_keys()
        if app_keys and not any(
            self.env.user.has_lhi_app_access(app_key) for app_key in app_keys
        ):
            raise AccessError(
                _("You do not have permission to access this application.")
            )
        return super()._get_action_dict()
