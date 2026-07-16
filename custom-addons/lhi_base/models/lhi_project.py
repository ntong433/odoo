# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LhiProject(models.Model):
    _name = 'lhi.project'
    _description = 'LHI Project Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Project Name', required=True, tracking=True)
    code = fields.Char(string='Project Code', required=True, default='/', tracking=True)
    award_id = fields.Many2one('lhi.award', string='Award Code', tracking=True)
    sector_id = fields.Many2one('lhi.sector', string='Sector', tracking=True)
    office_id = fields.Many2one('lhi.office', string='Office/Location', tracking=True)
    
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    active = fields.Boolean(string='Active', default=True, tracking=True)
    start_date = fields.Date(string='Effective Start Date', tracking=True)
    end_date = fields.Date(string='Effective End Date', tracking=True)

    _code_unique = models.Constraint(
        'unique(code)',
        'The Project Code must be unique!'
    )

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date and record.start_date > record.end_date:
                raise ValidationError(_("The start date cannot be later than the end date."))

    def unlink(self):
        for record in self:
            if record.active:
                raise ValidationError(_("Active projects cannot be deleted. Please archive them (set active to False) or set effective dates instead."))
            cost_centers = self.env['lhi.cost.center'].search([('project_id', '=', record.id)])
            if cost_centers:
                raise ValidationError(_("This project cannot be deleted because it is referenced by cost centres: %s. Please archive it instead.") % ', '.join(cost_centers.mapped('name')))
            activities = self.env['lhi.activity'].search([('project_id', '=', record.id)])
            if activities:
                raise ValidationError(_("This project cannot be deleted because it is referenced by activities: %s. Please archive it instead.") % ', '.join(activities.mapped('name')))
        return super(LhiProject, self).unlink()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code') or vals.get('code') == '/':
                vals['code'] = self.env['ir.sequence'].next_by_code('lhi.project') or '/'
        return super(LhiProject, self).create(vals_list)

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
