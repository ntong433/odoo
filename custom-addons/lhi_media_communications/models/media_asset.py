# -*- coding: utf-8 -*-
from odoo import models, fields

class MediaAsset(models.Model):
    _name = 'lhi.media.asset'
    _description = 'Media Asset'
    _inherits = {'ir.attachment': 'attachment_id'}
    _inherit = ['mail.thread', 'mail.activity.mixin']

    attachment_id = fields.Many2one('ir.attachment', string='Attachment', required=True, ondelete='cascade')
    
    asset_title = fields.Char(string='Asset Title', required=True, tracking=True)
    asset_type = fields.Selection([
        ('image', 'Image'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('document', 'Document'),
        ('poster', 'Poster'),
        ('graphic', 'Graphic'),
        ('radio_recording', 'Radio Recording'),
        ('consent_form', 'Consent Form'),
        ('other', 'Other')
    ], string='Asset Type', required=True, tracking=True)
    
    project_id = fields.Many2one('lhi.project', string='Project', tracking=True)
    activity_id = fields.Many2one('lhi.media.activity', string='Activity')
    success_story_id = fields.Many2one('lhi.media.success.story', string='Success Story')
    donor_id = fields.Many2one('lhi.grant.award', string='Donor')
    
    creator = fields.Char(string='Photographer/Creator')
    capture_date = fields.Date(string='Capture Date')
    location = fields.Char(string='Location')
    
    consent_status = fields.Selection([
        ('pending', 'Pending'),
        ('obtained', 'Obtained'),
        ('revoked', 'Revoked'),
        ('not_required', 'Not Required')
    ], string='Consent Status', default='pending', tracking=True)
    
    usage_restrictions = fields.Text(string='Usage Restrictions')
    caption = fields.Text(string='Caption')
    keywords = fields.Char(string='Keywords/Tags')
    
    expiry_date = fields.Date(string='Expiry/Review Date', tracking=True)

    sharepoint_site_id = fields.Char(string='SharePoint Site ID', readonly=True)
    sharepoint_drive_id = fields.Char(string='SharePoint Drive ID', readonly=True)
    sharepoint_item_id = fields.Char(string='SharePoint Item ID', readonly=True)
    sharepoint_parent_item_id = fields.Char(string='SharePoint Parent Item ID', readonly=True)
    sharepoint_web_url = fields.Char(string='SharePoint URL', readonly=True)
    sharepoint_last_sync_at = fields.Datetime(string='Last Sync', readonly=True)
    sharepoint_sync_status = fields.Selection([
        ('pending', 'Pending'),
        ('syncing', 'Syncing'),
        ('synced', 'Synced'),
        ('failed', 'Failed')
    ], string='Sync Status', default='pending', readonly=True)
