# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LhiSourcing(models.Model):
    _name = 'lhi.sourcing'
    _description = 'Procurement Sourcing Event'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Reference', required=True, default='New', tracking=True)
    title = fields.Char(string='Title', required=True, tracking=True)
    request_id = fields.Many2one('lhi.purchase.request', string='Purchase Request', required=True, ondelete='restrict', tracking=True)
    
    sourcing_type = fields.Selection([
        ('direct', 'Single-Source (Direct)'),
        ('rfq', 'Request for Quotation (RFQ)'),
        ('tender', 'Open Tender')
    ], string='Sourcing Type', required=True, tracking=True)
    
    justification = fields.Text(string='Single-Source Justification')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('published', 'Published / Bidding Open'),
        ('opening', 'Bid Opening'),
        ('technical', 'Technical Evaluation'),
        ('financial', 'Financial Evaluation'),
        ('recommended', 'Recommendation / Approval'),
        ('awarded', 'Awarded'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='request_id.currency_id', store=True)
    
    evaluator_ids = fields.One2many('lhi.sourcing.evaluator', 'sourcing_id', string='Evaluators')
    bid_ids = fields.One2many('lhi.bid', 'sourcing_id', string='Bids')
    
    evaluation_method = fields.Selection([
        ('lowest_responsive', 'Lowest Responsive Bid'),
        ('weighted', 'Weighted Scoring (Tech + Financial)')
    ], string='Evaluation Method', default='lowest_responsive', required=True, tracking=True)
    
    tech_weight = fields.Float(string='Technical Weight (%)', default=70.0)
    fin_weight = fields.Float(string='Financial Weight (%)', default=30.0)
    
    audit_file = fields.Html(string='Audit Summary', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('lhi.sourcing') or 'SRC-New'
        return super(LhiSourcing, self).create(vals_list)

    @api.constrains('tech_weight', 'fin_weight')
    def _check_weights(self):
        for rec in self:
            if rec.evaluation_method == 'weighted':
                if (rec.tech_weight + rec.fin_weight) != 100.0:
                    raise ValidationError(_("Technical and Financial weights must equal 100%."))

    def action_publish(self):
        self.write({'state': 'published'})
        self._log_audit("Sourcing event published.")

    def action_bid_opening(self):
        self.write({'state': 'opening'})
        self._log_audit("Bid opening commenced.")

    def action_technical_evaluation(self):
        for ev in self.evaluator_ids:
            if not ev.conflict_declared:
                raise ValidationError(_("All evaluators must declare conflict of interest before technical evaluation."))
        self.write({'state': 'technical'})
        self._log_audit("Technical evaluation commenced.")

    def action_financial_evaluation(self):
        self.write({'state': 'financial'})
        self._log_audit("Financial evaluation commenced.")

    def action_recommend(self):
        # Calculate scores and find recommended bid
        recommended_bid = False
        if self.evaluation_method == 'lowest_responsive':
            # Find cheapest compliant bid
            compliant_bids = self.bid_ids.filtered(lambda b: b.state == 'submitted' and b.technical_compliant)
            if not compliant_bids:
                raise ValidationError(_("No technically compliant bids found."))
            recommended_bid = min(compliant_bids, key=lambda b: b.financial_amount)
            
        elif self.evaluation_method == 'weighted':
            compliant_bids = self.bid_ids.filtered(lambda b: b.state == 'submitted' and b.technical_compliant and b.financial_amount > 0)
            if not compliant_bids:
                raise ValidationError(_("No valid compliant bids found for weighted evaluation."))
            
            lowest_price = min(compliant_bids.mapped('financial_amount'))
            for bid in compliant_bids:
                fin_score = (lowest_price / bid.financial_amount) * 100.0
                bid.financial_score = fin_score
                bid.weighted_score = (bid.technical_score * (self.tech_weight / 100.0)) + (fin_score * (self.fin_weight / 100.0))
                
            recommended_bid = max(compliant_bids, key=lambda b: b.weighted_score)
            
        if recommended_bid:
            for bid in self.bid_ids:
                if bid == recommended_bid:
                    bid.write({'state': 'recommended'})
                    self._log_audit(f"Bid from {bid.vendor_id.name} recommended for award.")
                elif bid.state != 'disqualified':
                    bid.write({'state': 'submitted'}) # Reset if needed, but not awarded
                    
        self.write({'state': 'recommended'})

    def action_award(self):
        rec_bid = self.bid_ids.filtered(lambda b: b.state == 'recommended')
        if not rec_bid:
            raise ValidationError(_("No recommended bid found to award."))
        rec_bid.write({'state': 'awarded'})
        self.write({'state': 'awarded'})
        self._log_audit(f"Sourcing event awarded to {rec_bid[0].vendor_id.name}.")

    def _log_audit(self, message):
        for rec in self:
            entry = f"<li><b>{fields.Datetime.now()}</b> - {self.env.user.name}: {message}</li>"
            rec.audit_file = (rec.audit_file or "<ul>") + entry + ("</ul>" if not rec.audit_file else "")

class LhiSourcingEvaluator(models.Model):
    _name = 'lhi.sourcing.evaluator'
    _description = 'Sourcing Evaluator'

    sourcing_id = fields.Many2one('lhi.sourcing', string='Sourcing Event', required=True, ondelete='cascade')
    user_id = fields.Many2one('res.users', string='Evaluator', required=True)
    conflict_declared = fields.Boolean(string='COI Declared', default=False)
    conflict_details = fields.Text(string='Conflict Details (if any)')

    def action_declare_no_conflict(self):
        if self.env.user != self.user_id:
            raise ValidationError(_("You can only declare conflicts for yourself."))
        self.write({'conflict_declared': True, 'conflict_details': 'No Conflict'})
        self.sourcing_id._log_audit(f"Evaluator {self.user_id.name} declared NO conflict of interest.")

    def action_declare_conflict(self):
        if self.env.user != self.user_id:
            raise ValidationError(_("You can only declare conflicts for yourself."))
        self.write({'conflict_declared': True})
        self.sourcing_id._log_audit(f"Evaluator {self.user_id.name} declared a potential conflict of interest.")
