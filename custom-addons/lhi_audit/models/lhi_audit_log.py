# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class LhiAuditLog(models.Model):
    _name = 'lhi.audit.log'
    _description = 'LHI Central Audit Log'
    _order = 'action_date desc, id desc'

    name = fields.Char(string='Event Name', compute='_compute_name', store=True)
    event_type = fields.Selection([
        ('login', 'User Login'),
        ('logout', 'User Logout'),
        ('access_denied', 'Access Denied (ACL/Rules)'),
        ('permission_change', 'Permission/Security Group Modification'),
        ('approval_action', 'Approval Matrix Action'),
        ('feature_flag_toggle', 'Feature Flag State Toggle'),
        ('sod_violation', 'Segregation of Duties Violation'),
        ('write_sensitive_field', 'Sensitive Configuration Write'),
    ], string='Event Type', required=True, index=True)

    user_id = fields.Many2one('res.users', string='Done By', required=True, index=True)
    action_date = fields.Datetime(string='Date/Time', default=fields.Datetime.now, required=True, index=True)
    
    res_model = fields.Char(string='Resource Model', index=True)
    res_id = fields.Integer(string='Resource ID', index=True)
    
    description = fields.Text(string='Description', required=True)
    old_value = fields.Text(string='Old Value')
    new_value = fields.Text(string='New Value')
    ip_address = fields.Char(string='IP Address')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    @api.depends('event_type', 'action_date')
    def _compute_name(self):
        for record in self:
            date_str = record.action_date.strftime('%Y-%m-%d %H:%M:%S') if record.action_date else ''
            record.name = f"[{record.event_type}] - {date_str}"

    @api.model
    def create_event(self, event_type, res_model=None, res_id=None, description=None, old_value=None, new_value=None):
        """Creates an audit event log record, automatically resolving requester details."""
        vals = {
            'event_type': event_type,
            'user_id': self.env.uid,
            'action_date': fields.Datetime.now(),
            'res_model': res_model,
            'res_id': res_id,
            'description': description or '',
            'old_value': str(old_value) if old_value is not None else False,
            'new_value': str(new_value) if new_value is not None else False,
            'company_id': self.env.company.id,
        }
        try:
            import odoo.http as http
            if http.request and hasattr(http.request, 'httprequest'):
                vals['ip_address'] = http.request.httprequest.remote_addr
        except Exception:
            pass
        return self.sudo().create(vals)
