# -*- coding: utf-8 -*-
from odoo import models, fields, api

class LhiFleetIncident(models.Model):
    _name = 'lhi.fleet.incident'
    _description = 'Fleet Incident Report'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Incident Reference', required=True, copy=False, default='New')
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle', required=True, tracking=True)
    trip_id = fields.Many2one('lhi.fleet.trip', string='Related Trip', tracking=True)
    driver_id = fields.Many2one('res.partner', string='Driver at time of incident', tracking=True)
    
    incident_date = fields.Datetime(string='Incident Date', required=True, default=fields.Datetime.now, tracking=True)
    incident_type = fields.Selection([
        ('accident', 'Traffic Accident'),
        ('breakdown', 'Mechanical Breakdown'),
        ('security', 'Security Incident'),
        ('theft', 'Theft / Vandalism'),
        ('other', 'Other')
    ], string='Type', required=True, tracking=True)
    
    description = fields.Text(string='Description of Incident', required=True)
    police_report_filed = fields.Boolean(string='Police Report Filed?', tracking=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('reported', 'Reported'),
        ('investigating', 'Under Investigation'),
        ('resolved', 'Resolved')
    ], string='Status', default='draft', tracking=True)
    
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('lhi.fleet.incident') or 'INC-New'
        return super(LhiFleetIncident, self).create(vals_list)

    def action_report(self):
        self.write({'state': 'reported'})
        
    def action_investigate(self):
        self.write({'state': 'investigating'})
        
    def action_resolve(self):
        self.write({'state': 'resolved'})
