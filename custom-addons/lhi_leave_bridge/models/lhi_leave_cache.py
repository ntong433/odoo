# -*- coding: utf-8 -*-
from odoo import models, fields, api
import requests
import logging

_logger = logging.getLogger(__name__)

class LhiLeaveCache(models.Model):
    _name = 'lhi.leave.cache'
    _description = 'Cached Leave Balances and Requests'
    
    user_id = fields.Many2one('res.users', string='User', required=True, index=True)
    entra_object_id = fields.Char(related='user_id.lhi_entra_object_id', store=True)
    
    annual_balance = fields.Float(string='Annual Leave Balance')
    sick_balance = fields.Float(string='Sick Leave Balance')
    
    is_stale = fields.Boolean(string='Is Data Stale?', default=True)
    last_sync_date = fields.Datetime(string='Last Successful Sync')
    
    @api.model
    def sync_leave_data_cron(self):
        self.env.user.check_lhi_app_access("hr_leave")
        # Fetch delta/balances for all users
        # For idempotency/retry, we log errors and leave `is_stale = True` if failure
        try:
            # Example API fetch
            # response = requests.get(config.leave_api_url)
            _logger.info("Successfully synced leave data (mock)")
        except Exception as e:
            _logger.error(f"Failed to sync leave data: {e}")
            self.search([]).write({'is_stale': True})

class LhiLeaveRequestCache(models.Model):
    _name = 'lhi.leave.request.cache'
    _description = 'Cached Leave Requests for Staff On Leave View'
    _order = 'start_date desc'
    
    external_id = fields.Char(string='External Leave ID', required=True, index=True)
    user_id = fields.Many2one('res.users', string='Employee', index=True)
    
    leave_type = fields.Char(string='Leave Type')
    start_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='End Date')
    
    status = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status')
