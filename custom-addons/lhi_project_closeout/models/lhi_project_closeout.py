# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LhiProjectCloseout(models.Model):
    _name = 'lhi.project.closeout'
    _description = 'Project Closeout Checklist'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Closeout Reference', required=True, tracking=True, default='New')
    project_id = fields.Many2one('lhi.project', string='Project', required=True, tracking=True)
    company_id = fields.Many2one(related='project_id.company_id', store=True)
    
    # Checklists
    programmatic_cleared = fields.Boolean(string='Programmatic Reports Cleared', tracking=True)
    procurement_cleared = fields.Boolean(string='Procurements Cleared/Closed', tracking=True)
    asset_cleared = fields.Boolean(string='Assets Disposed/Transferred', tracking=True)
    partner_cleared = fields.Boolean(string='Sub-Awards Closed', tracking=True)
    administrative_cleared = fields.Boolean(string='Administrative Obligations Cleared', tracking=True)
    financial_cleared = fields.Boolean(string='Financial Obligations Cleared', tracking=True)
    
    # Accounting Integration Mock
    enterprise_financial_figures = fields.Monetary(string='Verified Enterprise Accounting Final Figure', currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    archive_location = fields.Char(string='Physical/Digital Archive Location', tracking=True)
    lessons_learned = fields.Text(string='Lessons Learned', tracking=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('reviewed', 'Reviewed'),
        ('completed', 'Completed')
    ], string='Status', default='draft', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('lhi.project.closeout') or 'Closeout'
        return super(LhiProjectCloseout, self).create(vals_list)

    def action_start(self):
        self.state = 'in_progress'
        
    def action_review(self):
        self.state = 'reviewed'
        
    def action_complete(self):
        for record in self:
            if not all([record.programmatic_cleared, record.procurement_cleared, record.asset_cleared, 
                        record.partner_cleared, record.administrative_cleared, record.financial_cleared]):
                raise ValidationError(_("All closeout checklist items must be cleared before completion."))
            if not record.archive_location:
                raise ValidationError(_("Archive location is mandatory for final closeout."))
            record.state = 'completed'

class LhiProjectInherit(models.Model):
    _inherit = 'lhi.project'

    def write(self, vals):
        if 'active' in vals and not vals['active']:
            for project in self:
                closeout = self.env['lhi.project.closeout'].search([
                    ('project_id', '=', project.id),
                    ('state', '=', 'completed')
                ], limit=1)
                if not closeout:
                    raise ValidationError(_("Cannot archive/close project '%s' until a formal Project Closeout is completed.") % project.name)
        return super(LhiProjectInherit, self).write(vals)
