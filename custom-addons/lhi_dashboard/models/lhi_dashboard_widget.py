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
