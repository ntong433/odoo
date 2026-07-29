# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LhiPurchaseRequest(models.Model):
    _name = 'lhi.purchase.request'
    _description = 'Purchase Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='PR Reference', required=True, default='New', tracking=True)
    requester_id = fields.Many2one('res.users', string='Requester', required=True, default=lambda self: self.env.user, tracking=True)
    department_id = fields.Many2one('lhi.department', string='Department', tracking=True)
    office_id = fields.Many2one('lhi.office', string='Office', tracking=True)
    
    project_id = fields.Many2one('lhi.project', string='Project', tracking=True)
    donor_id = fields.Many2one('lhi.donor', string='Donor', tracking=True)
    award_id = fields.Many2one('lhi.award', string='Award', tracking=True)
    
    # We will assume lhi.activity exists in lhi_base/lhi_project_lifecycle (from earlier references)
    activity_id = fields.Many2one('lhi.activity', string='Activity', tracking=True)
    output_id = fields.Many2one(
        'lhi.results.element',
        string='Output',
        domain=[('element_type', '=', 'output')],
        tracking=True,
    )
    
    funding_source_id = fields.Many2one('lhi.funding.source', string='Funding Source', tracking=True)
    cost_center_id = fields.Many2one('lhi.cost.center', string='Cost Centre', tracking=True)
    budget_line_id = fields.Many2one('lhi.budget.line', string='Budget Line', tracking=True)
    
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    required_date = fields.Date(string='Required Date', required=True, tracking=True)
    justification = fields.Text(string='Business Justification', required=True)
    emergency_status = fields.Boolean(string='Emergency Status', default=False, tracking=True)
    suggested_vendors = fields.Text(string='Suggested Vendors')
    
    line_ids = fields.One2many('lhi.purchase.request.line', 'request_id', string='Products/Services')
    total_estimated_amount = fields.Monetary(string='Total Estimated Amount', compute='_compute_total_estimated_amount', store=True, currency_field='currency_id')
    
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    
    # Integration with lhi_approval_matrix
    lhi_approval_state = fields.Selection([
        ('draft', 'Draft'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('returned', 'Returned'),
        ('expired', 'Expired')
    ], string='Approval Status', default='draft', tracking=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted for Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('amended', 'Amended'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    procurement_method = fields.Selection([
        ('direct', 'Direct Sourcing'),
        ('rfq', 'Request for Quotation'),
        ('tender', 'Open Tender'),
    ], string='Procurement Method', compute='_compute_procurement_method', store=True)

    @api.depends('total_estimated_amount')
    def _compute_procurement_method(self):
        for req in self:
            if req.total_estimated_amount < 5000:
                req.procurement_method = 'direct'
            elif req.total_estimated_amount < 50000:
                req.procurement_method = 'rfq'
            else:
                req.procurement_method = 'tender'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('lhi.purchase.request') or 'PR-New'
        return super(LhiPurchaseRequest, self).create(vals_list)

    @api.depends('line_ids.estimated_amount')
    def _compute_total_estimated_amount(self):
        for req in self:
            req.total_estimated_amount = sum(req.line_ids.mapped('estimated_amount'))

    @api.constrains('project_id', 'required_date')
    def _check_grant_dates(self):
        for req in self:
            if req.project_id:
                if not req.project_id.is_effective(req.required_date):
                    raise ValidationError(_("The required date falls outside the effective dates of the selected project."))

    def action_submit(self):
        for req in self:
            if not req.line_ids:
                raise ValidationError(_("You must add at least one line item to the request."))
            # Here we trigger the approval matrix workflow
            approval_req = self.env['lhi.approval.request'].create({
                'res_model': self._name,
                'res_id': req.id,
                'document_type': 'purchase',
                'amount': req.total_estimated_amount,
                'currency_id': req.currency_id.id,
                'department_id': req.department_id.id,
                'office_id': req.office_id.id,
                'donor_id': req.donor_id.id,
                'award_id': req.award_id.id,
                'project_id': req.project_id.id,
                'funding_source_id': req.funding_source_id.id,
                'procurement_method': req.procurement_method,
                'company_id': req.company_id.id,
            })
            approval_req.action_submit()
            req.state = 'submitted'

    def action_cancel(self):
        for req in self:
            if (
                req.state == 'approved'
                and 'lhi.procurement.commitment' in self.env
            ):
                # Release commitment
                commitments = self.env['lhi.procurement.commitment'].search([('request_id', '=', req.id)])
                commitments.action_release()
            req.state = 'cancelled'

    def write(self, vals):
        if 'lhi_approval_state' in vals:
            if vals['lhi_approval_state'] == 'approved':
                vals['state'] = 'approved'
                # Creating procurement commitment is handled in overriding method in lhi_procurement_commitment
            elif vals['lhi_approval_state'] == 'rejected':
                vals['state'] = 'rejected'
            elif vals['lhi_approval_state'] == 'returned':
                vals['state'] = 'draft'
        return super(LhiPurchaseRequest, self).write(vals)


class LhiPurchaseRequestLine(models.Model):
    _name = 'lhi.purchase.request.line'
    _description = 'Purchase Request Line'

    request_id = fields.Many2one('lhi.purchase.request', string='Purchase Request', ondelete='cascade')
    name = fields.Char(string='Product/Service Description', required=True)
    specifications = fields.Text(string='Technical Specifications')
    quantity = fields.Float(string='Quantity', required=True, default=1.0)
    unit_price = fields.Monetary(string='Estimated Unit Price', currency_field='currency_id', required=True)
    estimated_amount = fields.Monetary(string='Estimated Amount', compute='_compute_amount', store=True, currency_field='currency_id')
    currency_id = fields.Many2one(related='request_id.currency_id', store=True)

    @api.depends('quantity', 'unit_price')
    def _compute_amount(self):
        for line in self:
            line.estimated_amount = line.quantity * line.unit_price
