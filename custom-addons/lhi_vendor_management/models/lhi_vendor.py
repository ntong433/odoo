# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta

class LhiVendor(models.Model):
    _name = 'lhi.vendor'
    _description = 'LHI Vendor'
    _inherits = {'res.partner': 'partner_id'}
    _inherit = ['mail.thread', 'mail.activity.mixin']

    partner_id = fields.Many2one('res.partner', string='Partner', required=True, ondelete='cascade')
    
    # Core Vendor Info
    tin = fields.Char(string='Tax Identification Number (TIN)', tracking=True)
    bank_details = fields.Text(string='Bank Details', tracking=True)
    ownership_information = fields.Text(string='Ownership/Directors Info', tracking=True)
    categories = fields.Char(string='Supply Categories', tracking=True)
    
    # Due Diligence
    due_diligence_status = fields.Selection([
        ('pending', 'Pending'),
        ('passed', 'Passed'),
        ('failed', 'Failed')
    ], string='Due Diligence Status', default='pending', tracking=True)
    
    sanctions_status = fields.Selection([
        ('clear', 'Clear'),
        ('flagged', 'Flagged / Excluded')
    ], string='Sanctions/Exclusion Status', default='clear', tracking=True)
    
    conflict_declared = fields.Boolean(string='Conflict of Interest Declared?', default=False, tracking=True)
    conflict_details = fields.Text(string='Conflict Details')
    
    document_ids = fields.Many2many('ir.attachment', string='Required Documents')
    
    expiry_date = fields.Date(string='Due Diligence Expiry', tracking=True)
    
    state = fields.Selection([
        ('draft', 'Draft / Onboarding'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved (Active)'),
        ('suspended', 'Suspended / Inactive')
    ], string='Status', default='draft', tracking=True)

    def action_submit_for_review(self):
        for rec in self:
            if not rec.tin or not rec.bank_details:
                raise ValidationError(_("TIN and Bank Details are required for review."))
            if not rec.document_ids:
                raise ValidationError(_("Please attach required onboarding documents."))
            rec.state = 'under_review'

    def action_approve(self):
        for rec in self:
            if rec.due_diligence_status != 'passed':
                raise ValidationError(_("Vendor must pass due diligence before approval."))
            if rec.sanctions_status == 'flagged':
                raise ValidationError(_("Vendor is flagged for sanctions and cannot be approved."))
            rec.state = 'approved'
            # Set expiry to 1 year from approval
            rec.expiry_date = fields.Date.today() + timedelta(days=365)

    def action_suspend(self):
        for rec in self:
            rec.state = 'suspended'

    @api.model
    def check_expiry_alerts(self):
        # Find vendors expiring in 30 days or already expired
        alert_date = fields.Date.today() + timedelta(days=30)
        expiring_vendors = self.search([
            ('state', '=', 'approved'),
            ('expiry_date', '<=', alert_date)
        ])
        for vendor in expiring_vendors:
            vendor.message_post(
                body=_("Alert: Vendor due diligence expires on %s. Please re-evaluate.") % vendor.expiry_date,
                subtype_xmlid='mail.mt_note'
            )
            # We could also schedule an activity here
            self.env['mail.activity'].create({
                'res_id': vendor.id,
                'res_model_id': self.env['ir.model'].search([('model', '=', 'lhi.vendor')], limit=1).id,
                'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                'summary': 'Vendor Due Diligence Expiring',
                'user_id': self.env.user.id,
                'date_deadline': vendor.expiry_date,
            })
