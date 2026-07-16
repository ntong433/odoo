# -*- coding: utf-8 -*-
from odoo import models, fields, api

class LhiDocumentMetadata(models.Model):
    _name = 'lhi.document.metadata'
    _description = 'Document Metadata Index'

    # The actual business bytes live in SharePoint.
    # Odoo only keeps the Immutable ID and indexed metadata for scoped queries.
    name = fields.Char(string='Filename', required=True)
    drive_item_id = fields.Char(string='SharePoint DriveItem ID', required=True, index=True)
    partition_id = fields.Many2one('lhi.sharepoint.partition', string='Storage Partition', required=True)
    
    # Indexed Metadata Columns
    project_code = fields.Char(string='ProjectCode', index=True)
    award_code = fields.Char(string='AwardCode', index=True)
    donor_code = fields.Char(string='DonorCode', index=True)
    document_category = fields.Char(string='DocumentCategory', index=True)
    document_status = fields.Char(string='DocumentStatus', index=True)
    reporting_year = fields.Char(string='ReportingYear', index=True)
    department = fields.Char(string='Department', index=True)
    office = fields.Char(string='Office', index=True)
    confidentiality = fields.Selection([
        ('public', 'Public'),
        ('internal', 'Internal'),
        ('restricted', 'Restricted')
    ], string='Confidentiality', default='internal')
    
    odoo_record_uuid = fields.Char(string='OdooRecordUUID', index=True)
    
    sp_created = fields.Datetime(string='SharePoint Created')
    sp_modified = fields.Datetime(string='SharePoint Modified')

    state = fields.Selection([
        ('active', 'Active'),
        ('deleted', 'Deleted/Moved')
    ], string='Sync State', default='active')

    @api.model
    def get_scoped_documents(self, project_code=None, category=None, year=None, limit=50, offset=0):
        # Demonstrates pagination and scoped querying
        domain = [('state', '=', 'active')]
        if project_code:
            domain.append(('project_code', '=', project_code))
        if category:
            domain.append(('document_category', '=', category))
        if year:
            domain.append(('reporting_year', '=', year))
            
        return self.search(domain, limit=limit, offset=offset)

class LhiDocumentReconciliation(models.Model):
    _name = 'lhi.document.reconciliation'
    _description = 'SharePoint Reconciliation Job'
    
    name = fields.Char(string='Reconciliation Task', required=True)
    last_run = fields.Datetime(string='Last Run')
    
    def run_reconciliation(self):
        # 1. Compare Odoo document metadata vs SharePoint DriveItems
        # 2. Identify Missing items, Orphaned files, Stale eTags, Failed Uploads
        # 3. Trigger alerts for Administrator
        self.last_run = fields.Datetime.now()
