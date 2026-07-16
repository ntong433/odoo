# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)

class LeaveWebhookController(http.Controller):

    @http.route('/api/leave/webhook', type='json', auth='public', methods=['POST'], csrf=False)
    def receive_leave_event(self):
        payload = request.jsonrequest
        event_type = payload.get('event_type')
        data = payload.get('data', {})
        
        # In production, validate security token / secret
        
        if event_type == 'leave.requested':
            # Create a unified inbox item for the approver
            approver_entra_id = data.get('approver_entra_id')
            approver = request.env['res.users'].sudo().search([('lhi_entra_object_id', '=', approver_entra_id)], limit=1)
            
            if approver:
                request.env['lhi.unified.inbox'].sudo().create({
                    'name': f"Leave Request from {data.get('employee_name')}",
                    'approver_id': approver.id,
                    'source_system': 'leave',
                    'external_reference': data.get('leave_id'),
                    'action_url': data.get('deep_link_url'),
                    'description': f"{data.get('leave_type')} from {data.get('start_date')} to {data.get('end_date')}"
                })
        elif event_type == 'leave.approved':
            # Update cache and inbox
            pass
            
        return {'status': 'success'}
