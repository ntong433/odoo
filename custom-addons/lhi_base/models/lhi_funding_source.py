# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LhiFundingSource(models.Model):
    _name = 'lhi.funding.source'
    _description = 'LHI Funding Source'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Funding Source Name', required=True, tracking=True)
    code = fields.Char(string='Funding Source Code', required=True, tracking=True)
    donor_id = fields.Many2one('lhi.donor', string='Donor', required=True, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    
    active = fields.Boolean(string='Active', default=True, tracking=True)
    start_date = fields.Date(string='Effective Start Date', tracking=True)
    end_date = fields.Date(string='Effective End Date', tracking=True)

    _code_unique = models.Constraint(
        'unique(code)',
        'The Funding Source Code must be unique!'
    )

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date and record.start_date > record.end_date:
                raise ValidationError(_("The start date cannot be later than the end date."))

    def unlink(self):
        for record in self:
            if record.active:
                raise ValidationError(_("Active funding sources cannot be deleted. Please archive them (set active to False) or set effective dates instead."))
            awards = self.env['lhi.award'].search([('funding_source_id', '=', record.id)])
            if awards:
                raise ValidationError(_("This funding source cannot be deleted because it is referenced by awards: %s. Please archive it instead.") % ', '.join(awards.mapped('name')))
        return super(LhiFundingSource, self).unlink()

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
