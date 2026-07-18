# -*- coding: utf-8 -*-
from odoo import api, fields, models

class LhiDashboardWidget(models.Model):
    _name = 'lhi.dashboard.widget'
    _description = 'LHI Dashboard Widget Configuration'
    _order = 'sequence, id'

    name = fields.Char(string="Widget Name", required=True)
    registry_key = fields.Char(string="Registry Key", required=True, 
                               help="The JS registry key for the Owl widget component.")
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)
    col_span = fields.Integer(string="Column Span", default=1, 
                              help="Width of the widget on desktop (e.g., 1 or 2)")
    
    # Access controls
    group_ids = fields.Many2many(
        'res.groups', 
        string="Allowed Groups",
        help="If specified, only users in these groups can see this widget."
    )

    _sql_constraints = [
        ('unique_registry_key', 'unique(registry_key)', 'The widget registry key must be unique!')
    ]

    # (key, label, menu XML ID, functional groups, synchronized department codes)
    # XML IDs and department codes are stable; translated display names and
    # deployment-specific database IDs must never become authorization inputs.
    _LHI_APP_DEFINITIONS = (
        ('pipeline', 'Pipeline', 'lhi_funding_opportunity.menu_lhi_funding_root', ('lhi_security.group_lhi_project_officer', 'lhi_security.group_lhi_project_manager', 'lhi_security.group_lhi_programme_director'), ('PIPELINE', 'PROGRAMME', 'PROGRAMMES')),
        ('procurement', 'Procurement', 'lhi_purchase_request.menu_lhi_procurement_root', ('lhi_security.group_lhi_procurement_officer', 'lhi_security.group_lhi_procurement_manager'), ('PROCUREMENT',)),
        ('operations', 'Operations', 'lhi_asset_management.menu_lhi_operations_root', ('lhi_security.group_lhi_supervisor', 'lhi_security.group_lhi_manager'), ('OPERATIONS',)),
        ('assets', 'Assets', 'lhi_asset_management.menu_lhi_asset', ('lhi_security.group_lhi_store_officer',), ('ASSET', 'ASSETS', 'OPERATIONS')),
        ('accounting', 'Accounting', 'account.menu_finance', ('lhi_security.group_lhi_finance_reviewer', 'lhi_accounting_base.group_lhi_accounting_sandbox'), ('ACCOUNTING', 'FINANCE')),
        ('meal', 'MEAL', 'lhi_results_framework.menu_lhi_meal_root', ('lhi_security.group_lhi_meal_officer', 'lhi_meal.group_lhi_meal_sensitive'), ('MEAL',)),
        ('inventory', 'Inventory', 'stock.menu_stock_root', ('lhi_security.group_lhi_store_officer',), ('INVENTORY', 'STORE')),
        ('fleet', 'Fleet', 'fleet.fleet_menu_root', ('lhi_security.group_lhi_fleet_officer',), ('FLEET', 'OPERATIONS')),
        ('approvals', 'Approvals', 'lhi_approval_matrix.menu_lhi_approvals_root', ('lhi_security.group_lhi_executive_approver', 'lhi_security.group_lhi_manager'), ('APPROVALS',)),
        ('projects', 'Projects & Grants', 'lhi_base.menu_lhi_project_root', ('lhi_security.group_lhi_project_officer', 'lhi_security.group_lhi_project_manager', 'lhi_security.group_lhi_programme_director'), ('PROJECTS', 'GRANTS', 'PROGRAMME', 'PROGRAMMES')),
        ('hr', 'Human Resources', 'hr.menu_hr_root', ('lhi_security.group_lhi_hr_officer',), ('HR', 'HUMAN_RESOURCES')),
        ('signatures', 'Signatures', 'lhi_signature_bridge.menu_lhi_opensign', ('lhi_security.group_lhi_procurement_officer', 'lhi_security.group_lhi_procurement_manager'), ('LEGAL', 'PROCUREMENT')),
        ('settings', 'Settings', 'base.menu_administration', ('base.group_system',), ()),
    )

    @api.model
    def get_user_widgets(self):
        """ Returns the list of active widgets accessible by the current user. """
        domain = [('active', '=', True)]
        widgets = self.search(domain)
        allowed_registry_keys = {
            'lhi_dashboard.my_tasks',
            'lhi_dashboard.my_approvals',
            'lhi_dashboard.notifications',
            'lhi_dashboard.accessible_modules',
        }
        
        result = []
        for widget in widgets:
            # If group_ids is empty, it's public (all users). 
            # If not, check if the current user is in any of the allowed groups.
            if widget.registry_key not in allowed_registry_keys:
                continue
            if not widget.group_ids or widget.group_ids & self.env.user.all_group_ids:
                result.append({
                    'id': widget.id,
                    'name': widget.name,
                    'registry_key': widget.registry_key,
                    # My Apps is a launcher section, not a KPI tile. Force the
                    # full dashboard row even when an older noupdate database
                    # record still contains the historical col_span=2 value.
                    'col_span': 12 if widget.registry_key == 'lhi_dashboard.accessible_modules' else widget.col_span,
                    'sequence': widget.sequence,
                })
        
        return result

    @api.model
    def get_accessible_apps(self):
        """Return authorized native menus for the current user's launcher.

        Native menu and action groups remain authoritative. Functional groups
        and department codes can only further narrow an already-visible menu.
        """
        user = self.env.user
        is_system = user.has_group('base.group_system')
        department_codes = {
            (code or '').strip().upper().replace(' ', '_')
            for code in user.lhi_department_ids.mapped('code')
        }
        visible_menu_ids = self.env['ir.ui.menu']._visible_menu_ids()
        apps = []

        for key, label, menu_xmlid, group_xmlids, department_codes_allowed in self._LHI_APP_DEFINITIONS:
            menu = self.env.ref(menu_xmlid, raise_if_not_found=False)
            if not menu or menu.id not in visible_menu_ids:
                continue

            group_match = any(user.has_group(xmlid) for xmlid in group_xmlids)
            department_match = bool(department_codes.intersection(department_codes_allowed))
            if not is_system and not (group_match or department_match):
                continue

            action = menu.action
            if action and 'group_ids' in action._fields and action.group_ids:
                if not is_system and not action.group_ids & user.all_group_ids:
                    continue

            apps.append({
                'key': key,
                'name': label,
                'menu_id': menu.id,
                'xmlid': menu_xmlid,
                'icon_url': f'/lhi_web_shell/static/src/img/module_icons/{key}.svg',
            })
        return apps

    @api.model
    def get_my_approval_summary(self):
        model_name = "lhi.approval.line"

        if model_name not in self.env or not self.env[model_name].check_access_rights('read', raise_exception=False):
            return {
                "available": False,
                "count": 0,
            }

        count = self.env[model_name].search_count([
            ("user_id", "=", self.env.user.id),
            ("status", "=", "pending"),
        ])

        return {
            "available": True,
            "count": count,
        }

    @api.model
    def get_quick_actions(self):
        """Returns allowed quick actions based on user's RBAC access."""
        actions = []
        
        # Quick Action: New Approval Request
        if 'lhi.approval.request' in self.env and self.env['lhi.approval.request'].check_access_rights('create', raise_exception=False):
            actions.append({
                'id': 'new_approval',
                'name': 'New Request',
                'description': 'Submit a new approval',
                'icon': 'fa-file-text-o',
                'action_type': 'ir.actions.act_window',
                'res_model': 'lhi.approval.request',
                'view_mode': 'form',
                'target': 'new'
            })
            
        return actions

    @api.model
    def global_search(self, query):
        """Searches across multiple models for the dashboard omnibar."""
        results = []
        limit = 5
        
        # Helper to search models safely
        def search_model(model_name, category, icon, domain=None, name_field='name', desc_field=None):
            if model_name in self.env and self.env[model_name].check_access_rights('read', raise_exception=False):
                base_domain = [(name_field, 'ilike', query)]
                if domain:
                    base_domain.extend(domain)
                records = self.env[model_name].search(base_domain, limit=limit)
                for rec in records:
                    desc = category
                    if desc_field:
                        parts = desc_field.split('.')
                        val = rec
                        for part in parts:
                            if hasattr(val, part):
                                val = getattr(val, part)
                            else:
                                val = None
                                break
                        if val:
                            desc = str(val)

                    results.append({
                        'id': f"{model_name}_{rec.id}",
                        'name': rec.display_name if hasattr(rec, 'display_name') else getattr(rec, name_field, 'Unknown'),
                        'description': desc,
                        'icon': icon,
                        'res_model': model_name,
                        'res_id': rec.id,
                        'category': category
                    })

        # Search Partners
        search_model('res.partner', 'Contact', 'user', [('is_company', '=', False)], desc_field='email')
        
        # Search Users
        search_model('res.users', 'User', 'user-circle', desc_field='login')
        
        # Search LHI Approvals
        search_model('lhi.approval.request', 'Approval Request', 'file-text-o')
        
        # Search Purchase Orders (if installed)
        search_model('purchase.order', 'Purchase Order', 'shopping-cart', desc_field='partner_id.name')
        
        # Search Projects (if installed)
        search_model('project.project', 'Project', 'puzzle-piece')
        
        # Search Tasks (if installed)
        search_model('project.task', 'Task', 'tasks', desc_field='project_id.name')

        return results
