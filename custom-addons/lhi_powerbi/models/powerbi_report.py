# -*- coding: utf-8 -*-
from odoo import models, fields, api

class LhiPowerBIReport(models.Model):
    _name = 'lhi.powerbi.report'
    _description = 'Power BI Embedded Report Registry'
    
    name = fields.Char(string='Report Title', required=True)
    report_id = fields.Char(string='Power BI Report ID', required=True, tracking=True)
    workspace_id = fields.Char(string='Power BI Workspace ID', required=True, tracking=True)
    
    description = fields.Text(string='Description')
    
    # RLS mapping - allowed groups
    allowed_group_ids = fields.Many2many('res.groups', string='Allowed User Groups')
    
    embed_url = fields.Char(string='Embed URL', compute='_compute_embed_url')
    
    @api.depends('report_id', 'workspace_id')
    def _compute_embed_url(self):
        for rec in self:
            if rec.report_id and rec.workspace_id:
                # Basic representation of embed URL structure
                rec.embed_url = f"https://app.powerbi.com/reportEmbed?reportId={rec.report_id}&groupId={rec.workspace_id}"
            else:
                rec.embed_url = False

    def action_view_report(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'lhi_powerbi.report_viewer',
            'name': self.name,
            'params': {
                'report_id': self.report_id,
                'workspace_id': self.workspace_id,
                'embed_url': self.embed_url,
                'record_id': self.id,
            }
        }
