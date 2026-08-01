# -*- coding: utf-8 -*-
from collections import defaultdict
from odoo import fields, models, api

from .res_users import LHI_APP_SELECTION


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    lhi_app_key = fields.Selection(
        selection=LHI_APP_SELECTION,
        string="LHI Application",
        index=True,
        help="Application entitlement required for this menu and its descendants.",
    )

    @api.model
    def _lhi_filter_app_menu_ids(self, visible_menu_ids):
        """Apply central application entitlements to native visible menus."""
        if not visible_menu_ids:
            return visible_menu_ids

        menus = self.sudo().browse(visible_menu_ids).exists()
        allowed_keys = set(self.env["res.users"].get_lhi_allowed_apps())
        blocked_ids = {
            menu.id
            for menu in menus
            if menu.lhi_app_key and menu.lhi_app_key not in allowed_keys
        }

        # Fail closed for untagged descendants of a denied tagged root.  This
        # also protects an older database while all menu records are upgraded.
        changed = True
        while changed:
            changed = False
            for menu in menus:
                if menu.id not in blocked_ids and menu.parent_id.id in blocked_ids:
                    blocked_ids.add(menu.id)
                    changed = True

        return frozenset(set(visible_menu_ids) - blocked_ids)

    @api.model
    def _visible_menu_ids(self, debug=False):
        """Return menu IDs visible to current user. For protected root, bypass group_ids restrictions."""
        if not self.env.user._lhi_is_protected_administrator():
            visible_menu_ids = super()._visible_menu_ids(debug=debug)
            return self._lhi_filter_app_menu_ids(visible_menu_ids)

        # For protected administrator: search ALL active menus, bypassing group_ids restriction
        menus = self.with_context({}).search_fetch(
            [('active', '=', True)],
            ['parent_id', 'action'], order='id',
        ).sudo()

        action_ids_by_model = defaultdict(list)
        for action in menus.mapped('action'):
            if action:
                action_ids_by_model[action._name].append(action.id)

        MODEL_BY_TYPE = {
            'ir.actions.act_window': 'res_model',
            'ir.actions.report': 'model',
            'ir.actions.server': 'model_name',
        }

        def exists_actions(model_name, action_ids):
            if model_name not in MODEL_BY_TYPE:
                return self.env[model_name].browse(action_ids).exists()
            records = self.env[model_name].sudo().with_context(active_test=False).search_fetch(
                [('id', 'in', action_ids)], [MODEL_BY_TYPE[model_name]], order='id',
            )
            if model_name == 'ir.actions.server':
                records.mapped('model_name')
            return records

        existing_actions = {
            action
            for model_name, action_ids in action_ids_by_model.items()
            for action in exists_actions(model_name, action_ids)
        }
        menu_ids = set(menus._ids)
        visible_ids = set()
        access = self.env['ir.model.access']

        for menu in menus:
            action = menu.action
            if not action or action not in existing_actions:
                continue
            model_fname = MODEL_BY_TYPE.get(action._name)
            if model_fname and not access.check(action[model_fname], 'read', False):
                continue
            menu_id = menu.id
            while menu_id not in visible_ids and menu_id in menu_ids:
                visible_ids.add(menu_id)
                menu = menu.parent_id
                menu_id = menu.id

        return self._lhi_filter_app_menu_ids(frozenset(visible_ids))
