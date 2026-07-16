# -*- coding: utf-8 -*-
from odoo import models, fields, api

class LhiIntegrationWebhook(models.Model):
    _name = 'lhi.integration.webhook'
    _description = 'Inbound Webhook Payload'
    _order = 'create_date desc'

    # Idempotency controls
    idempotency_key = fields.Char(string="Idempotency Key", index=True, required=True, 
                                  help="Client-provided unique identifier for this event.")
    source_system = fields.Char(string="Source System", required=True)
    
    event_type = fields.Char(string="Event Type", required=True)
    payload = fields.Text(string="JSON Payload", required=True)
    
    state = fields.Selection([
        ('received', 'Received'),
        ('processed', 'Processed'),
        ('ignored', 'Ignored/Duplicate'),
        ('error', 'Error')
    ], string="State", default='received', required=True)
    
    error_message = fields.Text(string="Error Message")

    _unique_idempotency = models.Constraint(
        "unique(idempotency_key, source_system)",
        "The idempotency key must be unique per source system to prevent duplicate processing.",
    )
