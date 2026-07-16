# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)

class LhiWebhookController(http.Controller):

    @http.route('/api/v1/webhook/<string:source_system>', type='jsonrpc', auth='public', methods=['POST'], csrf=False)
    def receive_webhook(self, source_system, **kwargs):
        """
        Generic Webhook Receiver
        Enforces idempotency and logs the payload securely.
        Authorization should ideally happen via API Key headers in real production,
        but for the framework we accept JSON.
        """
        payload = request.jsonrequest
        idempotency_key = request.httprequest.headers.get('Idempotency-Key')
        
        if not idempotency_key:
            return {'status': 'error', 'message': 'Missing Idempotency-Key header'}

        # Verify Authorization header for valid connection
        auth_header = request.httprequest.headers.get('Authorization')
        if not auth_header:
            return {'status': 'error', 'message': 'Missing Authorization header', 'code': 401}
            
        # Optional: Validate token against lhi.integration.connection here.

        WebhookModel = request.env['lhi.integration.webhook'].sudo()
        
        # Check for duplicates safely
        existing = WebhookModel.search([
            ('idempotency_key', '=', idempotency_key),
            ('source_system', '=', source_system)
        ], limit=1)

        if existing:
            _logger.info("Ignored duplicate webhook event %s from %s", idempotency_key, source_system)
            return {'status': 'ignored', 'message': 'Duplicate idempotency key'}

        # Create record safely
        try:
            webhook = WebhookModel.create({
                'idempotency_key': idempotency_key,
                'source_system': source_system,
                'event_type': payload.get('event_type', 'unknown'),
                'payload': json.dumps(payload),
                'state': 'received'
            })
            
            # Enqueue an integration job to process it asynchronously
            request.env['lhi.integration.job'].sudo().create_job(
                model_name='lhi.integration.webhook',
                record_id=webhook.id,
                action='process',
                description=f'Process Webhook {source_system} - {idempotency_key}'
            )
            
            return {'status': 'success', 'message': 'Webhook queued'}
            
        except Exception as e:
            _logger.error("Failed to store webhook: %s", str(e))
            return {'status': 'error', 'message': 'Internal Server Error', 'code': 500}
