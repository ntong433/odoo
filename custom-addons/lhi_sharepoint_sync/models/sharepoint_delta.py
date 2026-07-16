# -*- coding: utf-8 -*-
from odoo import models, fields, api

class LhiSharepointDelta(models.Model):
    _name = 'lhi.sharepoint.delta'
    _description = 'SharePoint Delta Link State'

    partition_id = fields.Many2one('lhi.sharepoint.partition', string='Partition', required=True)
    delta_link = fields.Char(string='Latest Delta Link', required=True)
    last_sync = fields.Datetime(string='Last Synchronized')
    
    @api.model
    def run_delta_sync(self):
        # Scheduled job to process Graph DriveItem Delta
        # This will query Graph using the delta_link, process changes/deletions,
        # and update the delta_link for the next run.
        pass
