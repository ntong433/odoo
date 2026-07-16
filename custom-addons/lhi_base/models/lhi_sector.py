# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LhiSector(models.Model):
    _name = 'lhi.sector'
    _description = 'LHI Technical Sector'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Sector Name', required=True, tracking=True)
    code = fields.Char(string='Sector Code', required=True, tracking=True)
    programme_id = fields.Many2one('lhi.programme', string='Programme', tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    
    active = fields.Boolean(string='Active', default=True, tracking=True)
    start_date = fields.Date(string='Effective Start Date', tracking=True)
    end_date = fields.Date(string='Effective End Date', tracking=True)

    _code_unique = models.Constraint(
        'unique(code)',
        'The Sector Code must be unique!'
    )

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date and record.start_date > record.end_date:
                raise ValidationError(_("The start date cannot be later than the end date."))

    def unlink(self):
        for record in self:
            if record.active:
                raise ValidationError(_("Active technical sectors cannot be deleted. Please archive them (set active to False) or set effective dates instead."))
            projects = self.env['lhi.project'].search([('sector_id', '=', record.id)])
            if projects:
                raise ValidationError(_("This technical sector cannot be deleted because it is referenced by projects: %s. Please archive it instead.") % ', '.join(projects.mapped('name')))
        return super(LhiSector, self).unlink()

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
