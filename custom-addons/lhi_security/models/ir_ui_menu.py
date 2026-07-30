# -*- coding: utf-8 -*-
from collections import defaultdict
from odoo import models, api


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _visible_menu_ids(self, debug=False):
        """Return menu IDs visible to current user. For protected root, bypass group_ids restrictions."""
        if not self.env.user._lhi_is_protected_administrator():
            return super()._visible_menu_ids(debug=debug)

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

        return frozenset(visible_ids)
