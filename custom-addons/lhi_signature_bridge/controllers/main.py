# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json

class OpenSignController(http.Controller):

    @http.route('/api/opensign/callback', type='json', auth='public', methods=['POST'], csrf=False)
    def opensign_callback(self):
        # 1. Parse JSON payload
        # 2. Extract request_id or reference
        # 3. Find lhi.opensign.request
        # 4. Call request.process_callback()
        
        payload = request.jsonrequest
        request_ref = payload.get('reference')
        status = payload.get('status')
        error = payload.get('error')
        
        # Security: validate webhook signature/token in real world
        
        if not request_ref or not status:
            return {'status': 'error', 'message': 'Missing reference or status'}
            
        req = request.env['lhi.opensign.request'].sudo().search([('name', '=', request_ref)], limit=1)
        if not req:
            return {'status': 'error', 'message': 'Request not found'}
            
        req.process_callback(status, error=error)
        return {'status': 'success'}
