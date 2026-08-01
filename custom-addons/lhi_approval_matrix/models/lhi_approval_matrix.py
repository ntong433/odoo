# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime

class LhiApprovalMatrix(models.Model):
    _name = 'lhi.approval.matrix'
    _description = 'LHI Approval Matrix Configuration'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name, id'

    name = fields.Char(string='Matrix Name', required=True, tracking=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    MEMO_APPROVAL_CONTRACT_VERSION = 1

    # Criteria
    document_type = fields.Selection([
        ('purchase', 'Purchase Request'),
        ('payment', 'Payment Voucher'),
        ('travel', 'Travel Request'),
        ('leave', 'Leave Request'),
        ('memo', 'Internal Memo'),
    ], string='Document Type', required=True, tracking=True)

    min_amount = fields.Float(string='Minimum Amount', default=0.0, tracking=True)
    max_amount = fields.Float(string='Maximum Amount', default=0.0, help='Set to 0.0 for no limit', tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.company.currency_id)

    department_ids = fields.Many2many('lhi.department', string='Departments')
    office_ids = fields.Many2many('lhi.office', string='Offices/Locations')
    donor_ids = fields.Many2many('lhi.donor', string='Donors')
    award_ids = fields.Many2many('lhi.award', string='Grants/Awards')
    project_ids = fields.Many2many('lhi.project', string='Projects')
    funding_source_ids = fields.Many2many('lhi.funding.source', string='Funding Sources')

    procurement_method = fields.Selection([
        ('direct', 'Direct Sourcing'),
        ('rfq', 'Request for Quotation'),
        ('tender', 'Open Tender'),
    ], string='Procurement Method', tracking=True)

    # Workflow Steps
    line_ids = fields.One2many('lhi.approval.matrix.line', 'matrix_id', string='Approval Stages', copy=True)

    @api.constrains('min_amount', 'max_amount')
    def _check_amounts(self):
        for record in self:
            if record.max_amount > 0.0 and record.min_amount > record.max_amount:
                raise ValidationError(_("Minimum amount cannot be greater than maximum amount."))

    @api.model
    def find_matching_matrix(self, document_type, amount=0.0, currency_id=None, department_id=None, office_id=None,
                             donor_id=None, award_id=None, project_id=None, funding_source_id=None, procurement_method=None, company_id=None):
        """Finds the most specific active approval matrix based on provided criteria."""
        company_id = company_id or self.env.company.id
        currency_id = currency_id or self.env.company.currency_id.id
        
        # Build search domain for criteria
        domain = [
            ('active', '=', True),
            ('document_type', '=', document_type),
            ('company_id', '=', company_id),
            ('currency_id', '=', currency_id),
            ('min_amount', '<=', amount),
        ]
        
        matrices = self.search(domain)
        
        # Filter matching records based on Many2many and Selection criteria
        matched_matrices = []
        for matrix in matrices:
            if matrix.max_amount > 0.0 and amount > matrix.max_amount:
                continue
            if matrix.department_ids and department_id not in matrix.department_ids.ids:
                continue
            if matrix.office_ids and office_id not in matrix.office_ids.ids:
                continue
            if matrix.donor_ids and donor_id not in matrix.donor_ids.ids:
                continue
            if matrix.award_ids and award_id not in matrix.award_ids.ids:
                continue
            if matrix.project_ids and project_id not in matrix.project_ids.ids:
                continue
            if matrix.funding_source_ids and funding_source_id not in matrix.funding_source_ids.ids:
                continue
            if matrix.procurement_method and procurement_method != matrix.procurement_method:
                continue
            matched_matrices.append(matrix)
            
        # Return the match with the lowest sequence (highest priority)
        if matched_matrices:
            matched_matrices.sort(key=lambda m: m.sequence)
            return matched_matrices[0]
        return self.env['lhi.approval.matrix']

    @api.model
    def _lhi_get_memo_approval_route(
        self, memo, amount=0.0, currency=None, department=None, office=None, award=None, project=None
    ):
        """Service contract v1 method for resolving Memo approval route."""
        matrix = memo.memo_category_id.approval_matrix_id if hasattr(memo, "memo_category_id") else False
        if not matrix:
            matrix = self.find_matching_matrix(
                document_type="memo",
                amount=amount,
                currency_id=currency.id if currency else None,
                department_id=department.id if department else None,
                office_id=office.id if office else None,
                award_id=award.id if award else None,
                project_id=project.id if project else None,
                company_id=memo.company_id.id if memo else self.env.company.id,
            )
        if not matrix or not matrix.active:
            return {
                "contract_version": self.MEMO_APPROVAL_CONTRACT_VERSION,
                "matrix_id": False,
                "matrix_name": False,
                "stages": [],
            }
        stages = []
        for line in matrix.line_ids.sorted("sequence"):
            approvers = line._lhi_resolve_approver_users(memo) if hasattr(line, "_lhi_resolve_approver_users") else line.approver_ids
            stages.append({
                "line_id": line.id,
                "sequence": line.sequence,
                "name": line.name,
                "approval_type": line.approval_type,
                "approver_group_id": line.approver_group_id.id,
                "approver_user_ids": approvers.ids,
            })
        return {
            "contract_version": self.MEMO_APPROVAL_CONTRACT_VERSION,
            "matrix_id": matrix.id,
            "matrix_name": matrix.name,
            "stages": stages,
        }


class LhiApprovalMatrixLine(models.Model):
    _name = 'lhi.approval.matrix.line'
    _description = 'LHI Approval Matrix Stage / Line'
    _order = 'sequence, id'

    matrix_id = fields.Many2one('lhi.approval.matrix', string='Approval Matrix', ondelete='cascade', required=True)
    sequence = fields.Integer(string='Sequence/Step', default=10)
    name = fields.Char(string='Stage Name', required=True)
    
    approver_group_id = fields.Many2one('res.groups', string='Approver Role/Group', required=True)
    approver_ids = fields.Many2many('res.users', string='Specific Approvers', help='Optional specific users. If set, only these users can approve, provided they belong to the specified group.')
    
    approval_type = fields.Selection([
        ('any', 'Any Approver'),
        ('all', 'All Approvers'),
    ], string='Approval Type', default='any', required=True, help='Any: one person from the group/approvers is enough. All: all assigned approvers must approve.')
    
    timeout_days = fields.Integer(string='Timeout (Days)', default=3, help='Number of days before this approval stage expires')
    escalation_user_id = fields.Many2one('res.users', string='Escalation Approver', help='User to escalate to if timeout is reached')

    def _lhi_resolve_approver_users(self, request):
        """Extension point for manager-based or other approved resolver strategies."""
        self.ensure_one()
        approver_users = self.env['res.users'].search([
            ('active', '=', True),
            ('group_ids', 'in', [self.approver_group_id.id]),
        ])
        if self.approver_ids:
            approver_users = approver_users.filtered(
                lambda user: user.id in self.approver_ids.ids
            )
        # Technical root accounts must never automatically appear as candidate approvers
        return approver_users.filtered(
            lambda user: not user._lhi_is_protected_administrator()
        )


class LhiSodRule(models.Model):
    _name = 'lhi.sod.rule'
    _description = 'Segregation of Duties Conflict Rule'
    _inherit = ['mail.thread']

    name = fields.Char(string='Rule Name', required=True, tracking=True)
    group_1_id = fields.Many2one('res.groups', string='Role/Group 1', required=True, tracking=True)
    group_2_id = fields.Many2one('res.groups', string='Role/Group 2', required=True, tracking=True)
    is_active = fields.Boolean(string='Active', default=True, tracking=True)
    description = fields.Text(string='Description')

    _group_uniq = models.Constraint(
        'unique(group_1_id, group_2_id)',
        'Conflict pair must be unique!'
    )

    @api.constrains('group_1_id', 'group_2_id')
    def _check_different_groups(self):
        for record in self:
            if record.group_1_id == record.group_2_id:
                raise ValidationError(_("A Segregation of Duties rule cannot reference the same group twice."))

    @api.model
    def check_user_conflicts(self, user):
        """Checks if a user is assigned conflicting roles according to active SoD rules."""
        if not user:
            return
        active_rules = self.search([('is_active', '=', True)])
        user_groups = user.group_ids
        for rule in active_rules:
            if rule.group_1_id in user_groups and rule.group_2_id in user_groups:
                raise ValidationError(_(
                    "Segregation of Duties Conflict Detected!\n"
                    "User '%s' cannot be assigned to both '%s' and '%s' simultaneously."
                ) % (user.name, rule.group_1_id.name, rule.group_2_id.name))


class LhiApprovalDelegation(models.Model):
    _name = 'lhi.approval.delegation'
    _description = 'LHI Approval Delegation'
    _inherit = ['mail.thread']

    name = fields.Char(string='Description', compute='_compute_name')
    delegator_id = fields.Many2one('res.users', string='Delegator', required=True, default=lambda self: self.env.user, tracking=True)
    delegatee_id = fields.Many2one('res.users', string='Delegatee', required=True, tracking=True)
    start_date = fields.Datetime(string='Start Date', required=True, tracking=True)
    end_date = fields.Datetime(string='End Date', required=True, tracking=True)
    active = fields.Boolean(string='Active', default=True, tracking=True)
    
    document_type = fields.Selection([
        ('all', 'All Documents'),
        ('purchase', 'Purchase Request'),
        ('payment', 'Payment Voucher'),
        ('travel', 'Travel Request'),
        ('leave', 'Leave Request'),
    ], string='Document Type Constraint', default='all', required=True, tracking=True)

    @api.depends('delegator_id', 'delegatee_id')
    def _compute_name(self):
        for record in self:
            record.name = _("Delegation from %s to %s") % (record.delegator_id.name, record.delegatee_id.name)

    @api.constrains('start_date', 'end_date', 'delegator_id', 'delegatee_id')
    def _check_delegation_invariants(self):
        for record in self:
            if record.delegator_id == record.delegatee_id:
                raise ValidationError(_("You cannot delegate approval authority to yourself."))
            if record.start_date > record.end_date:
                raise ValidationError(_("Start date cannot be later than end date."))

    @api.model
    def get_delegated_user(self, user_id, document_type, date=None):
        """Returns the delegated user if an active delegation exists, otherwise returns original user."""
        date = date or fields.Datetime.now()
        delegation = self.search([
            ('delegator_id', '=', user_id),
            ('active', '=', True),
            ('start_date', '<=', date),
            ('end_date', '>=', date),
            ('document_type', 'in', ['all', document_type])
        ], limit=1)
        if delegation:
            return delegation.delegatee_id
        return self.env['res.users'].browse(user_id)
