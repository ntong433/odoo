# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LhiOffice(models.Model):
    _name = 'lhi.office'
    _description = 'LHI Office / Field Location'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Office Name', required=True, tracking=True)
    code = fields.Char(string='Office Code', required=True, tracking=True)
    office_type = fields.Selection([
        ('head', 'Head Office'),
        ('field', 'Field Office'),
        ('satellite', 'Satellite Office')
    ], string='Office Type', default='field', required=True, tracking=True)
    
    parent_id = fields.Many2one('lhi.office', string='Parent Office', tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    
    active = fields.Boolean(string='Active', default=True, tracking=True)
    start_date = fields.Date(string='Effective Start Date', tracking=True)
    end_date = fields.Date(string='Effective End Date', tracking=True)

    _code_unique = models.Constraint(
        'unique(code)',
        'The Office Code must be unique!'
    )

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date and record.start_date > record.end_date:
                raise ValidationError(_("The start date cannot be later than the end date."))

    def unlink(self):
        for record in self:
            if record.active:
                raise ValidationError(_("Active offices cannot be deleted. Please archive them (set active to False) or set effective dates instead."))
            child_offices = self.env['lhi.office'].search([('parent_id', '=', record.id)])
            if child_offices:
                raise ValidationError(_("This office cannot be deleted because it is referenced as a parent by other offices: %s. Please archive it instead.") % ', '.join(child_offices.mapped('name')))
            projects = self.env['lhi.project'].search([('office_id', '=', record.id)])
            if projects:
                raise ValidationError(_("This office cannot be deleted because it is referenced by projects: %s. Please archive it instead.") % ', '.join(projects.mapped('name')))
        return super(LhiOffice, self).unlink()

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
