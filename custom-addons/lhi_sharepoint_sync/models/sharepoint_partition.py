# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class LhiSharepointPartition(models.Model):
    _name = 'lhi.sharepoint.partition'
    _description = 'SharePoint Logical Storage Partition'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Partition Name', required=True)
    domain = fields.Char(string='Domain (e.g., Finance, HR)')
    year = fields.Char(string='Year')
    project = fields.Char(string='Project Code')
    
    site_id = fields.Char(string='SharePoint Site ID', required=True)
    drive_id = fields.Char(string='SharePoint Drive ID', required=True)
    root_folder_id = fields.Char(string='Root Folder ID', required=True)
    
    active = fields.Boolean(string='Active', default=True)
    read_only = fields.Boolean(string='Read-Only', default=False)
    
    item_count = fields.Integer(string='Active Item Count', default=0, tracking=True)
    warning_threshold = fields.Integer(string='Warning Threshold', default=4000)
    routing_threshold = fields.Integer(string='Routing Threshold', default=4500)

    @api.model
    def select_partition(self, domain, year, project):
        """ Automatically select or provision a partition that is safe (below threshold) """
        partition = self.search([
            ('domain', '=', domain),
            ('year', '=', year),
            ('project', '=', project),
            ('active', '=', True),
            ('read_only', '=', False),
            ('item_count', '<', 4000)
        ], limit=1)
        if not partition:
            # Depending on business logic, raise warning or provision new one
            # Here we will raise an alert, assuming a pre-provisioned partition is required
            raise ValueError(_('No safe active partition found for %s / %s / %s. Library capacity threshold reached.') % (domain, year, project))
        return partition

    def _check_capacity(self):
        for partition in self:
            if partition.item_count >= partition.warning_threshold:
                # Trigger administrator alerts
                partition.message_post(body=_('Warning: Partition %s is approaching the 5000-item SharePoint list-view threshold.') % partition.name)
            if partition.item_count >= partition.routing_threshold:
                partition.read_only = True
                partition.message_post(body=_('Alert: Partition %s has exceeded the routing threshold and is now marked Read-Only.') % partition.name)
