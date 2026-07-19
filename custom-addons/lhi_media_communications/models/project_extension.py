# -*- coding: utf-8 -*-
from odoo import models, fields

class LhiProjectExtension(models.Model):
    _inherit = 'lhi.project'

    media_request_ids = fields.One2many('lhi.media.request', 'project_id', string='Media Requests')
    media_activity_ids = fields.One2many('lhi.media.activity', 'project_id', string='Media Activities')
    media_success_story_ids = fields.One2many('lhi.media.success.story', 'project_id', string='Success Stories')
    media_asset_ids = fields.One2many('lhi.media.asset', 'project_id', string='Media Assets')
    
    media_request_count = fields.Integer(compute='_compute_media_counts', string='Media Requests Count')
    media_activity_count = fields.Integer(compute='_compute_media_counts', string='Media Activities Count')
    media_success_story_count = fields.Integer(compute='_compute_media_counts', string='Success Stories Count')
    media_asset_count = fields.Integer(compute='_compute_media_counts', string='Media Assets Count')

    def _compute_media_counts(self):
        for project in self:
            project.media_request_count = len(project.media_request_ids)
            project.media_activity_count = len(project.media_activity_ids)
            project.media_success_story_count = len(project.media_success_story_ids)
            project.media_asset_count = len(project.media_asset_ids)

    def action_view_media_requests(self):
        self.ensure_one()
        return {
            'name': 'Media Requests',
            'type': 'ir.actions.act_window',
            'res_model': 'lhi.media.request',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_media_activities(self):
        self.ensure_one()
        return {
            'name': 'Media Activities',
            'type': 'ir.actions.act_window',
            'res_model': 'lhi.media.activity',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_media_success_stories(self):
        self.ensure_one()
        return {
            'name': 'Success Stories',
            'type': 'ir.actions.act_window',
            'res_model': 'lhi.media.success.story',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_media_assets(self):
        self.ensure_one()
        return {
            'name': 'Media Assets',
            'type': 'ir.actions.act_window',
            'res_model': 'lhi.media.asset',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
