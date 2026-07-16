# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class LhiFleetTrip(models.Model):
    _name = 'lhi.fleet.trip'
    _description = 'Trip Request & Authorization'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Trip Reference', required=True, copy=False, default='New')
    
    # People
    traveller_id = fields.Many2one('res.users', string='Primary Traveller', required=True, tracking=True, default=lambda self: self.env.user)
    driver_id = fields.Many2one('res.partner', string='Assigned Driver', tracking=True)
    
    # Asset
    vehicle_id = fields.Many2one('fleet.vehicle', string='Assigned Vehicle', tracking=True)
    
    # Details
    purpose = fields.Text(string='Trip Purpose', required=True)
    lhi_project_id = fields.Many2one('lhi.project', string='Project', tracking=True)
    lhi_activity_id = fields.Many2one('lhi.workplan.activity', string='Activity', tracking=True)
    
    location_from = fields.Char(string='Departure Location', required=True)
    location_to = fields.Char(string='Destination', required=True)
    
    date_start = fields.Datetime(string='Start Date', required=True, tracking=True)
    date_end = fields.Datetime(string='Expected End Date', required=True, tracking=True)
    
    expected_distance = fields.Float(string='Expected Distance (km)')
    security_requirements = fields.Text(string='Security / Convoy Requirements')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted for Authorization'),
        ('approved', 'Approved'),
        ('in_progress', 'In Progress'),
        ('done', 'Completed'),
        ('cancel', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('lhi.fleet.trip') or 'TRP-New'
        return super(LhiFleetTrip, self).create(vals_list)

    def action_submit(self):
        self.write({'state': 'submitted'})
        
    def action_approve(self):
        self.write({'state': 'approved'})
        
    def action_start(self):
        self.write({'state': 'in_progress'})
        
    def action_done(self):
        self.write({'state': 'done'})
        
    def action_cancel(self):
        self.write({'state': 'cancel'})
