# -*- coding: utf-8 -*-
from odoo import models, fields, api, exceptions

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

    @api.model
    def get_user_widgets(self):
        """ Returns the list of active widgets accessible by the current user. """
        domain = [('active', '=', True)]
        widgets = self.search(domain)
        
        result = []
        for widget in widgets:
            # If group_ids is empty, it's public (all users). 
            # If not, check if the current user is in any of the allowed groups.
            if not widget.group_ids or any(group in self.env.user.groups_id for group in widget.group_ids):
                result.append({
                    'id': widget.id,
                    'name': widget.name,
                    'registry_key': widget.registry_key,
                    'col_span': widget.col_span,
                    'sequence': widget.sequence,
                })
        
        return result

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
