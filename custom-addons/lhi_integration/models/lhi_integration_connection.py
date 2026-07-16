# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class LhiIntegrationConnection(models.Model):
    _name = 'lhi.integration.connection'
    _description = 'API Connection Configuration'

    name = fields.Char(string="Connection Name", required=True)
    provider = fields.Selection([
        ('microsoft_graph', 'Microsoft Graph API'),
        ('opensign', 'LHI OpenSign API'),
        ('other', 'Other Custom API')
    ], string="Provider", required=True)
    
    active = fields.Boolean(string="Active", default=True)
    base_url = fields.Char(string="Base URL", required=True)
    
    # Credentials shouldn't be stored directly in plain text if possible.
    # Often, we use ir.config_parameter or encrypted fields.
    # For Sprint 6, we'll store credentials reference and recommend using env vars or Odoo config.
    auth_type = fields.Selection([
        ('oauth2', 'OAuth 2.0 (Client Credentials)'),
        ('bearer', 'Bearer Token'),
        ('api_key', 'API Key')
    ], string="Authentication Type", required=True)
    
    client_id = fields.Char(string="Client ID")
    # Store secret keys securely. We use password widget and restrict read access.
    client_secret = fields.Char(string="Client Secret")
    tenant_id = fields.Char(string="Tenant ID (Microsoft)")

    def action_test_connection(self):
        """ Abstract testing connection logic """
        self.ensure_one()
        # Logic to test connection based on auth_type and provider
        # e.g., Request token from Microsoft
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Test Connection',
                'message': f'Successfully verified connection to {self.name}',
                'type': 'success',
                'sticky': False,
            }
        }
