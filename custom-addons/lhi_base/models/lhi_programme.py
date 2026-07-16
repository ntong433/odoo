# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LhiProgramme(models.Model):
    _name = 'lhi.programme'
    _description = 'LHI Programme'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Programme Name', required=True, tracking=True)
    code = fields.Char(string='Programme Code', required=True, tracking=True)
    description = fields.Text(string='Description')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    
    active = fields.Boolean(string='Active', default=True, tracking=True)
    start_date = fields.Date(string='Effective Start Date', tracking=True)
    end_date = fields.Date(string='Effective End Date', tracking=True)

    _code_unique = models.Constraint(
        'unique(code)',
        'The Programme Code must be unique!'
    )

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date and record.start_date > record.end_date:
                raise ValidationError(_("The start date cannot be later than the end date."))

    def unlink(self):
        for record in self:
            if record.active:
                raise ValidationError(_("Active programmes cannot be deleted. Please archive them (set active to False) or set effective dates instead."))
            sectors = self.env['lhi.sector'].search([('programme_id', '=', record.id)])
            if sectors:
                raise ValidationError(_("This programme cannot be deleted because it is referenced by technical sectors: %s. Please archive it instead.") % ', '.join(sectors.mapped('name')))
        return super(LhiProgramme, self).unlink()

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
