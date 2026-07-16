# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json

class GraphNotificationsController(http.Controller):

    @http.route('/lhi/graph/notifications', type='http', auth='public', methods=['POST'], csrf=False)
    def handle_graph_notifications(self, **kwargs):
        """ Webhook endpoint for Microsoft Graph Change Notifications """
        
        # 1. Validation of Subscription Challenge
        validation_token = kwargs.get('validationToken')
        if validation_token:
            # Microsoft expects the token returned back as plain text (200 OK)
            return request.make_response(validation_token, headers=[('Content-Type', 'text/plain')])
            
        # 2. Process Notifications
        payload = request.httprequest.get_data(as_text=True)
        try:
            data = json.loads(payload)
        except Exception:
            return request.make_response('Invalid JSON', status=400)
            
        # Optional: Validate Notification Client State
        # Secret check to ensure the payload is genuinely from Microsoft
        # client_state = data.get('value', [{}])[0].get('clientState')
        # if client_state != EXPECTED_STATE: return 403
        
        # 3. Queue Actual Processing Asynchronously
        # Since Microsoft requires a response within 3 seconds, we just log/queue it here.
        # Delta synchronization cron handles the actual pulling of changes.
        
        # Return a successful response quickly
        return request.make_response('Accepted', status=202)
