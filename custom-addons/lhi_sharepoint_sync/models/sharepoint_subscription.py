# -*- coding: utf-8 -*-
from odoo import models, fields, api

class LhiSharepointSubscription(models.Model):
    _name = 'lhi.sharepoint.subscription'
    _description = 'SharePoint Graph Webhook Subscription'

    name = fields.Char(string='Subscription ID', required=True, copy=False)
    resource = fields.Char(string='Resource Path', required=True)
    expiration_date = fields.Datetime(string='Expiration Date', required=True)
    client_state = fields.Char(string='Client State Secret', required=True, copy=False)
    
    active = fields.Boolean(default=True)
    
    @api.model
    def renew_subscriptions(self):
        # Scheduled job to renew subscriptions before they expire
        # Normally involves a Graph API POST to update the expirationDateTime
        subs = self.search([('active', '=', True)])
        for sub in subs:
            # Stub: API call to Microsoft Graph
            # If successful, update expiration_date
            pass
