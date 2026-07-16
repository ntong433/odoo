# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LhiDonor(models.Model):
    _name = 'lhi.donor'
    _description = 'LHI Donor'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Donor Name', required=True, tracking=True)
    code = fields.Char(string='Donor Code', required=True, tracking=True)
    donor_type = fields.Selection([
        ('bilateral', 'Bilateral'),
        ('multilateral', 'Multilateral'),
        ('foundation', 'Foundation'),
        ('corporate', 'Corporate'),
        ('ngo', 'NGO'),
        ('other', 'Other')
    ], string='Donor Type', default='bilateral', required=True, tracking=True)
    
    contact_name = fields.Char(string='Contact Person', tracking=True)
    email = fields.Char(string='Email')
    phone = fields.Char(string='Phone')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    
    active = fields.Boolean(string='Active', default=True, tracking=True)
    start_date = fields.Date(string='Effective Start Date', tracking=True)
    end_date = fields.Date(string='Effective End Date', tracking=True)

    _code_unique = models.Constraint(
        'unique(code)',
        'The Donor Code must be unique!'
    )

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date and record.start_date > record.end_date:
                raise ValidationError(_("The start date cannot be later than the end date."))

    def unlink(self):
        for record in self:
            if record.active:
                raise ValidationError(_("Active donors cannot be deleted. Please archive them (set active to False) or set effective dates instead."))
            funding_sources = self.env['lhi.funding.source'].search([('donor_id', '=', record.id)])
            if funding_sources:
                raise ValidationError(_("This donor cannot be deleted because it is referenced by funding sources: %s. Please archive it instead.") % ', '.join(funding_sources.mapped('name')))
        return super(LhiDonor, self).unlink()

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
