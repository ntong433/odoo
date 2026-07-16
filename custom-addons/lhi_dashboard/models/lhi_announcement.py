# -*- coding: utf-8 -*-
from odoo import models, fields, api

class LhiAnnouncement(models.Model):
    _name = 'lhi.announcement'
    _description = 'LHI Organizational Announcement'
    _order = 'date_start desc, id desc'

    name = fields.Char(string="Title", required=True)
    content = fields.Html(string="Content", required=True, sanitize=True)
    active = fields.Boolean(string="Active", default=True)
    
    date_start = fields.Date(string="Start Date", default=fields.Date.context_today, required=True)
    date_end = fields.Date(string="End Date", help="Leave empty to display indefinitely.")
    
    type = fields.Selection([
        ('info', 'Information'),
        ('warning', 'Warning'),
        ('success', 'Success'),
        ('danger', 'Urgent')
    ], string="Type", default='info', required=True)

    @api.model
    def get_active_announcements(self):
        """ Returns current active announcements. """
        today = fields.Date.context_today(self)
        domain = [
            ('active', '=', True),
            ('date_start', '<=', today),
            '|', ('date_end', '=', False), ('date_end', '>=', today)
        ]
        
        announcements = self.search(domain, limit=5)
        
        return [{
            'id': a.id,
            'title': a.name,
            'content': a.content,
            'type': a.type,
            'date': a.date_start,
        } for a in announcements]
