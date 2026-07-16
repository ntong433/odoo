# -*- coding: utf-8 -*-
from odoo import models, fields, api

class LhiProjectExtension(models.Model):
    _inherit = 'lhi.project'

    odoo_project_id = fields.Many2one('project.project', string='Execution Project', tracking=True)

    def action_activate_project(self):
        """ Override to automatically create an Odoo Project execution workspace upon activation """
        res = super(LhiProjectExtension, self).action_activate_project()
        for record in self:
            if not record.odoo_project_id:
                # Create corresponding Odoo project
                odoo_project = self.env['project.project'].create({
                    'name': f"[{record.code}] {record.name}",
                    'company_id': record.company_id.id,
                    'user_id': record.focal_pm_id.id if record.focal_pm_id else False,
                })
                record.odoo_project_id = odoo_project.id
        return res

class StandardProjectExtension(models.Model):
    _inherit = 'project.project'

    lhi_project_id = fields.Many2one('lhi.project', string='LHI Project Code', tracking=True)
