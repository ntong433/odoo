# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from odoo.addons.lhi_security.models.res_users import LHI_APP_SELECTION


_logger = logging.getLogger(__name__)

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
    app_key = fields.Selection(
        selection=LHI_APP_SELECTION,
        string="LHI Application",
        index=True,
        help="Application entitlement required for an application-specific widget.",
    )
    is_public_internal = fields.Boolean(
        string="Visible to Internal Users",
        default=False,
        help="Explicitly expose a non-application widget to authenticated internal users.",
    )

    _sql_constraints = [
        ('unique_registry_key', 'unique(registry_key)', 'The widget registry key must be unique!')
    ]

    @api.constrains("registry_key", "app_key", "is_public_internal", "group_ids")
    def _check_widget_access_configuration(self):
        for widget in self:
            configured_modes = sum(
                bool(value)
                for value in (
                    widget.app_key,
                    widget.is_public_internal,
                    widget.group_ids,
                )
            )
            if configured_modes > 1:
                raise ValidationError(
                    _(
                        "Choose one widget access mode: application, internal, "
                        "or explicit groups."
                    )
                )
            if widget.registry_key.startswith("lhi_app.") and not widget.app_key:
                raise ValidationError(
                    _("An application widget must have an LHI Application entitlement.")
                )

    # (app key, label, root menu XML ID, local icon URL). Authorization comes
    # exclusively from res.users.has_lhi_app_access(app_key).
    _LHI_APP_DEFINITIONS = (
        ('operations', 'Operations', 'lhi_dashboard.menu_lhi_operations_hub', '/lhi_web_shell/static/src/img/module_icons/operations.svg'),
        ('hub', 'HUB', 'lhi_hub_management.menu_lhi_hub', '/lhi_web_shell/static/src/img/module_icons/inventory.svg'),
        ('assets', 'Asset Register', 'lhi_asset_management.menu_lhi_asset', '/lhi_web_shell/static/src/img/module_icons/assets.svg'),
        ('procurement', 'Procurement', 'lhi_purchase_request.menu_lhi_procurement_root', '/lhi_web_shell/static/src/img/module_icons/procurement.svg'),
        ('inventory', 'Inventory', 'stock.menu_stock_root', '/lhi_web_shell/static/src/img/module_icons/inventory.svg'),
        ('fleet', 'Fleet', 'fleet.menu_root', '/lhi_web_shell/static/src/img/module_icons/fleet.svg'),
        ('programs_grants', 'Programs & Grants', 'lhi_base.menu_lhi_root', '/lhi_web_shell/static/src/img/module_icons/grants.svg'),
        ('approvals', 'Approvals', 'lhi_approval_matrix.menu_lhi_approvals_root', '/lhi_web_shell/static/src/img/module_icons/approvals.svg'),
        ('reports', 'Reports', 'lhi_reporting_hub.menu_lhi_reporting_hub_root', '/lhi_web_shell/static/src/img/module_icons/reporting.svg'),
        ('power_bi', 'Power BI', 'lhi_powerbi.menu_lhi_powerbi_root', '/lhi_web_shell/static/src/img/module_icons/analytics.svg'),
        ('media', 'Media & Communications', 'lhi_media_communications.menu_lhi_media_root', '/lhi_web_shell/static/src/img/module_icons/media.svg'),
        ('meal', 'MEAL', 'lhi_results_framework.menu_lhi_meal_root', '/lhi_web_shell/static/src/img/module_icons/meal.svg'),
        ('memo', 'Memos', 'lhi_memo_management.menu_lhi_memo_root', '/lhi_web_shell/static/src/img/module_icons/memos.svg'),
        ('signatures', 'Signatures', 'lhi_signature_bridge.menu_lhi_opensign', '/lhi_web_shell/static/src/img/module_icons/signatures.svg'),
        ('hr_leave', 'HR & Leave', 'lhi_leave_bridge.menu_lhi_leave_root', '/lhi_web_shell/static/src/img/module_icons/leave.svg'),
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
            'lhi_dashboard.quick_actions',
        }
        
        result = []
        for widget in widgets:
            if widget.registry_key not in allowed_registry_keys:
                continue
            if widget.app_key:
                visible = self.env.user.has_lhi_app_access(widget.app_key)
            elif widget.is_public_internal:
                visible = self.env.user.has_group("base.group_user")
            elif widget.group_ids:
                visible = bool(widget.group_ids & self.env.user.all_group_ids)
            else:
                visible = False
            if visible:
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
    def _deduplicate_dashboard_apps(self, apps):
        """Return one launcher card per stable app entry."""
        unique_apps = []
        seen_keys = set()
        for app in apps:
            stable_key = app.get('xmlid') or app.get('key') or (str(app.get('menu_id')) if app.get('menu_id') else None)
            if not stable_key:
                continue
            if stable_key in seen_keys:
                _logger.warning("Duplicate dashboard module removed: %s", stable_key)
                continue
            seen_keys.add(stable_key)
            unique_apps.append(app)
        return unique_apps

    @api.model
    def _get_accessible_module_entries(self, definitions, include_mappings=False):
        """
        Secure backend method determining module availability.
        Relies purely on the current user's visible_menu_ids for native ACL checking.
        Does not read menu.action to prevent AccessError on ir.actions.act_window.
        """
        user = self.env.user
        is_erp_admin = user.has_group("lhi_security.group_lhi_erp_admin")
        visible_menu_ids = self.env['ir.ui.menu']._visible_menu_ids()
        
        apps = []
        warnings = []

        # 1. Base static apps definition
        for key, label, menu_xmlid, icon_path in definitions:
            menu = self.env.ref(menu_xmlid, raise_if_not_found=False)
            if not menu:
                continue
            if not user.has_lhi_app_access(key):
                continue

            # Native ACL visibility check - Authoritative
            if menu.id not in visible_menu_ids:
                if is_erp_admin:
                    warnings.append(f"Module '{label}' is authorized by functional rules but native ACLs block it.")
                continue

            apps.append({
                'key': key,
                'name': label,
                'menu_id': menu.id,
                'xmlid': menu_xmlid,
                'icon_url': icon_path,
            })

        # 2. Dynamic Sidebar Role Mapping (Manager / Director specific)
        if include_mappings and 'lhi.sidebar.role.mapping' in self.env:
            # Use tight sudo() to read mapping configurations without granting users access to the config model
            mappings = self.env['lhi.sidebar.role.mapping'].sudo().search([
                ('active', '=', True),
                '|',
                ('company_ids', '=', False),
                ('company_ids', 'in', user.company_ids.ids),
            ])
            for mapping in mappings:
                if not mapping.menu_id:
                    continue

                if mapping.app_key and user.has_lhi_app_access(mapping.app_key):
                    menu = self.env['ir.ui.menu'].browse(mapping.menu_id.id)
                    if menu.id not in visible_menu_ids:
                        if is_erp_admin:
                            warnings.append(f"Role Mapping '{mapping.name}' grants access to '{menu.name}' but native ACLs/record rules deny access.")
                        continue
                    
                    menu_xml_id_dict = menu.get_external_id()
                    menu_xmlid = menu_xml_id_dict.get(menu.id)
                    apps.append({
                        'key': mapping.app_key,
                        'name': menu.name,
                        'menu_id': menu.id,
                        'xmlid': menu_xmlid,
                        'icon_url': '/lhi_web_shell/static/src/img/module_icons/operations.svg',
                    })

        unique_apps = self._deduplicate_dashboard_apps(apps)
        return {
            'apps': unique_apps,
            'warnings': warnings
        }

    @api.model
    def get_accessible_apps(self):
        """Return authorized native menus for the current user's launcher."""
        return self._get_accessible_module_entries(
            self._LHI_APP_DEFINITIONS, include_mappings=True
        )

    @api.model
    def get_my_approval_summary(self):
        if not self.env.user.has_lhi_app_access("approvals"):
            return {"available": False, "count": 0}
        model_name = "lhi.approval.request.line"

        if model_name not in self.env or not self.env[model_name].check_access_rights('read', raise_exception=False):
            return {
                "available": False,
                "count": 0,
            }

        try:
            count = self.env[model_name].search_count([
                ("approver_ids", "in", [self.env.user.id]),
                ("state", "=", "pending"),
            ])
        except AccessError:
            return {
                "available": False,
                "count": 0,
            }

        return {
            "available": True,
            "count": count,
        }

    @api.model
    def get_quick_actions(self):
        """Returns allowed quick actions based on user's RBAC access."""
        actions = []
        
        # Quick Action: New Approval Request
        if (
            self.env.user.has_lhi_app_access("approvals")
            and 'lhi.approval.request' in self.env
            and self.env['lhi.approval.request'].check_access_rights('create', raise_exception=False)
        ):
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

        if (
            'lhi.memo' in self.env
            and self.env.user.has_group('lhi_security.group_lhi_employee')
            and self.env['lhi.memo'].check_access_rights('create', raise_exception=False)
        ):
            actions.append({
                'id': 'raise_memo',
                'name': 'Raise Memo',
                'description': 'Start a Word-based internal memo',
                'icon': 'fa-file-word-o',
                'action_type': 'ir.actions.act_window',
                'res_model': 'lhi.memo',
                'view_mode': 'form',
                'target': 'current',
            })
            
        return actions

    @api.model
    def global_search(self, query):
        """Searches across multiple models for the dashboard omnibar."""
        results = []
        limit = 5
        
        # Helper to search models safely
        def search_model(model_name, category, icon, domain=None, name_field='name', desc_field=None, app_key=None):
            try:
                if app_key and not self.env.user.has_lhi_app_access(app_key):
                    return
                if model_name not in self.env:
                    return
                model = self.env[model_name]
                if not model.check_access_rights('read', raise_exception=False):
                    return
                base_domain = [(name_field, 'ilike', query)]
                if domain:
                    base_domain.extend(domain)
                records = model.search(base_domain, limit=limit)
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
            except AccessError:
                _logger.info(
                    "Dashboard search source %s is unavailable to user %s.",
                    model_name,
                    self.env.uid,
                )

        # Search Partners
        search_model('res.partner', 'Contact', 'user', [('is_company', '=', False)], desc_field='email')
        
        # Search LHI Approvals
        search_model('lhi.approval.request', 'Approval Request', 'file-text-o', app_key='approvals')
        
        # Search Purchase Orders (if installed)
        search_model('purchase.order', 'Purchase Order', 'shopping-cart', desc_field='partner_id.name', app_key='procurement')
        
        # Search Projects (if installed)
        search_model('project.project', 'Project', 'puzzle-piece', app_key='programs_grants')
        
        # Search Tasks (if installed)
        search_model('project.task', 'Task', 'tasks', desc_field='project_id.name', app_key='programs_grants')

        return results

    _LHI_OPERATIONS_DEFINITIONS = (
        ('hub', 'HUB', 'lhi_hub_management.menu_lhi_hub', '/lhi_web_shell/static/src/img/module_icons/inventory.svg'),
        ('procurement', 'Procurement', 'lhi_purchase_request.menu_lhi_procurement_root', '/lhi_web_shell/static/src/img/module_icons/procurement.svg'),
        ('assets', 'Asset Register', 'lhi_asset_management.menu_lhi_asset', '/lhi_web_shell/static/src/img/module_icons/assets.svg'),
        ('inventory', 'Inventory', 'stock.menu_stock_root', '/lhi_web_shell/static/src/img/module_icons/inventory.svg'),
        ('fleet', 'Fleet', 'fleet.menu_root', '/lhi_web_shell/static/src/img/module_icons/fleet.svg'),
    )

    @api.model
    def get_accessible_operations(self):
        """
        Returns the operational modules accessible to the current user.
        """
        self.env.user.check_lhi_app_access("operations")
        res = self._get_accessible_module_entries(
            self._LHI_OPERATIONS_DEFINITIONS, include_mappings=False
        )
        # Operations API expects 'modules' instead of 'apps'
        return {
            'modules': res['apps'],
            'warnings': res['warnings']
        }
