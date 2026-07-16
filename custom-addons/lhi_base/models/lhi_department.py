# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LhiDepartment(models.Model):
    _name = 'lhi.department'
    _description = 'LHI Department / Unit'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Department Name', required=True, tracking=True)
    code = fields.Char(string='Department/Unit Code', required=True, tracking=True)
    parent_id = fields.Many2one('lhi.department', string='Parent Department/Unit', tracking=True)
    manager_id = fields.Many2one('res.users', string='Manager', tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    
    active = fields.Boolean(string='Active', default=True, tracking=True)
    start_date = fields.Date(string='Effective Start Date', tracking=True)
    end_date = fields.Date(string='Effective End Date', tracking=True)

    _code_unique = models.Constraint(
        'unique(code)',
        'The Department/Unit Code must be unique!'
    )

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date and record.start_date > record.end_date:
                raise ValidationError(_("The start date cannot be later than the end date."))

    def unlink(self):
        for record in self:
            if record.active:
                raise ValidationError(_("Active departments/units cannot be deleted. Please archive them (set active to False) or set effective dates instead."))
            child_depts = self.env['lhi.department'].search([('parent_id', '=', record.id)])
            if child_depts:
                raise ValidationError(_("This department/unit cannot be deleted because it is referenced as a parent by other departments/units: %s. Please archive it instead.") % ', '.join(child_depts.mapped('name')))
        return super(LhiDepartment, self).unlink()

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
