# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LhiAward(models.Model):
    _name = 'lhi.award'
    _description = 'LHI Award'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Award Title', required=True, tracking=True)
    code = fields.Char(string='Award Code', required=True, default='/', tracking=True)
    funding_source_id = fields.Many2one('lhi.funding.source', string='Funding Source', required=True, tracking=True)
    
    amount = fields.Float(string='Total Value/Budget', tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    
    active = fields.Boolean(string='Active', default=True, tracking=True)
    start_date = fields.Date(string='Effective Start Date', tracking=True)
    end_date = fields.Date(string='Effective End Date', tracking=True)

    _code_unique = models.Constraint(
        'unique(code)',
        'The Award Code must be unique!'
    )

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date and record.start_date > record.end_date:
                raise ValidationError(_("The start date cannot be later than the end date."))

    def unlink(self):
        for record in self:
            if record.active:
                raise ValidationError(_("Active awards cannot be deleted. Please archive them (set active to False) or set effective dates instead."))
            projects = self.env['lhi.project'].search([('award_id', '=', record.id)])
            if projects:
                raise ValidationError(_("This award cannot be deleted because it is referenced by projects: %s. Please archive it instead.") % ', '.join(projects.mapped('name')))
        return super(LhiAward, self).unlink()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code') or vals.get('code') == '/':
                vals['code'] = self.env['ir.sequence'].next_by_code('lhi.award') or '/'
        return super(LhiAward, self).create(vals_list)

    def is_effective(self, date=None):
        self.ensure_one()
        if not self.active:
            return False
        date = date or fields.Date.context_today(self)
        if self.start_date and date < self.start_date:
            return False
        if self.end_date and date > self.end_date:
            return False
        return True
