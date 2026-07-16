# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class LhiDocumentMigrationJob(models.Model):
    _name = 'lhi.document.migration.job'
    _description = 'Attachment Migration Batch Job'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Batch Reference', required=True, default='New')
    
    is_dry_run = fields.Boolean(string='Dry Run Mode', default=True,
        help="If checked, the system classifies files and identifies destinations without actually uploading.")
    batch_size = fields.Integer(string='Batch Size', default=500)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('classifying', 'Classifying'),
        ('classified', 'Classified (Ready)'),
        ('migrating', 'Migrating'),
        ('completed', 'Completed'),
        ('paused', 'Paused')
    ], string='Status', default='draft', tracking=True)
    
    mapping_ids = fields.One2many('lhi.document.migration.mapping', 'job_id', string='File Mappings')
    
    # Classification Stats
    total_found = fields.Integer(string='Total Evaluated', compute='_compute_stats')
    count_business = fields.Integer(string='Business Documents', compute='_compute_stats')
    count_technical = fields.Integer(string='Technical/Retain', compute='_compute_stats')
    count_duplicate = fields.Integer(string='Duplicates', compute='_compute_stats')
    count_missing = fields.Integer(string='Missing Files', compute='_compute_stats')
    count_migrated = fields.Integer(string='Successfully Migrated', compute='_compute_stats')
    
    def _compute_stats(self):
        for job in self:
            job.total_found = len(job.mapping_ids)
            job.count_business = len(job.mapping_ids.filtered(lambda m: m.classification == 'business'))
            job.count_technical = len(job.mapping_ids.filtered(lambda m: m.classification == 'technical'))
            job.count_duplicate = len(job.mapping_ids.filtered(lambda m: m.classification == 'duplicate'))
            job.count_missing = len(job.mapping_ids.filtered(lambda m: m.classification == 'missing'))
            job.count_migrated = len(job.mapping_ids.filtered(lambda m: m.state == 'verified'))

    def action_classify(self):
        """ Scans ir.attachment and builds mappings based on linked models. """
        self.state = 'classifying'
        # Logic to iterate over ir.attachment, detect checksum duplicates, filter technical vs business.
        # ...
        self.state = 'classified'
        
    def action_run_migration(self):
        self.state = 'migrating'
        for mapping in self.mapping_ids.filtered(lambda m: m.state in ['draft', 'failed']):
            if self.is_dry_run:
                # Calculate destination and expected checksum only
                mapping.state = 'dry_run_ok'
            else:
                # Upload to SP, verify metadata, store DriveItem
                mapping.action_upload()
        if not self.mapping_ids.filtered(lambda m: m.state in ['draft', 'failed', 'migrating']):
            self.state = 'completed'

    def action_pause(self):
        self.state = 'paused'
        
    def action_local_purge(self):
        """ Separate controlled purge. Only deletes ir.attachment binary content if state is verified. """
        # We enforce an environment variable check just in case, per user rules
        if not self.env['ir.config_parameter'].sudo().get_param('DOCUMENT_LOCAL_PURGE_ENABLED'):
            raise UserError(_("Local purging is disabled globally. Check environment settings."))
            
        for mapping in self.mapping_ids.filtered(lambda m: m.state == 'verified'):
            # Clear binary data safely while retaining the metadata record and SP link
            pass

class LhiDocumentMigrationMapping(models.Model):
    _name = 'lhi.document.migration.mapping'
    _description = 'Attachment Migration Mapping'

    job_id = fields.Many2one('lhi.document.migration.job', ondelete='cascade')
    attachment_id = fields.Many2one('ir.attachment', string='Local Attachment', required=True)
    res_model = fields.Char(related='attachment_id.res_model', store=True)
    
    classification = fields.Selection([
        ('business', 'Business Document'),
        ('technical', 'Technical / Retain'),
        ('temporary', 'Temporary'),
        ('duplicate', 'Duplicate'),
        ('orphan', 'Orphaned'),
        ('missing', 'Corrupt/Missing')
    ], string='Classification', required=True)
    
    destination_partition_id = fields.Many2one('lhi.sharepoint.partition', string='Target SP Partition')
    
    local_checksum = fields.Char(string='Local Checksum')
    sp_drive_item_id = fields.Char(string='SharePoint DriveItem ID')
    sp_checksum = fields.Char(string='SharePoint Checksum')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('dry_run_ok', 'Dry Run OK'),
        ('migrating', 'Uploading'),
        ('verified', 'Verified on SP'),
        ('failed', 'Failed')
    ], string='State', default='draft')
    
    def action_upload(self):
        # Stub: perform API upload
        # if SP checksum matches local checksum:
        # self.state = 'verified'
        # self.attachment_id.write({'lhi_drive_item_id': self.sp_drive_item_id})
        pass
        
    def action_rollback(self):
        # Detach mapping if needed
        self.sp_drive_item_id = False
        self.state = 'draft'
