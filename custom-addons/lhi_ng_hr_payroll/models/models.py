# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class LhiPayrollStructure(models.Model):
    _name = 'lhi.payroll.structure'
    _description = 'Effective-dated Salary Structure'

    name = fields.Char(string='Structure Name', required=True)
    rule_ids = fields.One2many('lhi.payroll.rule', 'structure_id', string='Salary Rules')
    date_start = fields.Date(string='Effective From', required=True)
    date_end = fields.Date(string='Effective To')
    active = fields.Boolean(default=True)

class LhiPayrollRule(models.Model):
    _name = 'lhi.payroll.rule'
    _description = 'Payroll Rule'

    name = fields.Char(string='Rule Name', required=True)
    code = fields.Char(string='Code', required=True)
    structure_id = fields.Many2one('lhi.payroll.structure', required=True)
    rule_type = fields.Selection([
        ('allowance', 'Allowance'),
        ('deduction', 'Deduction'),
        ('statutory_paye', 'PAYE Tax'),
        ('statutory_pension', 'Pension Deduction')
    ], string='Rule Type', required=True)
    amount = fields.Float(string='Fixed Amount')
    percentage = fields.Float(string='Percentage (%)')
    
class LhiPayslip(models.Model):
    _name = 'lhi.payslip'
    _description = 'Employee Payslip'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Payslip Ref')
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    structure_id = fields.Many2one('lhi.payroll.structure', string='Salary Structure', required=True)
    date_from = fields.Date(string='Date From', required=True)
    date_to = fields.Date(string='Date To', required=True)
    
    net_pay = fields.Monetary(string='Net Pay', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('verified', 'Verified'),
        ('approved', 'Approved'),
        ('done', 'Paid/Posted'),
        ('reversed', 'Reversed')
    ], string='Status', default='draft', tracking=True)
    
    move_id = fields.Many2one('account.move', string='Accounting Entry', readonly=True)

    def action_verify(self):
        self.state = 'verified'
        
    def action_approve(self):
        self.state = 'approved'
        
    def action_post_journals(self):
        # Prevent accounting posts if Accounting is inactive
        self.env['lhi.accounting.feature.gate'].check_accounting_enabled()
        self.state = 'done'

class LhiPayslipBatch(models.Model):
    _name = 'lhi.payslip.batch'
    _description = 'Payslip Batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Batch Name', required=True)
    date_start = fields.Date(string='Period Start', required=True)
    date_end = fields.Date(string='Period End', required=True)
    payslip_ids = fields.One2many('lhi.payslip', compute='_compute_payslips')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('done', 'Posted')
    ], string='Status', default='draft', tracking=True)

    def _compute_payslips(self):
        for batch in self:
            batch.payslip_ids = self.env['lhi.payslip'].search([
                ('date_from', '>=', batch.date_start),
                ('date_to', '<=', batch.date_end)
            ])
            
    def action_approve(self):
        self.state = 'approved'
        
    def action_post_batch(self):
        self.env['lhi.accounting.feature.gate'].check_accounting_enabled()
        self.state = 'done'
