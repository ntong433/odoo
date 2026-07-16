# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

class LhiReportingJob(models.Model):
    _name = 'lhi.reporting.job'
    _description = 'Data Extraction and Sync Job'
    _inherit = ['mail.thread']

    name = fields.Char(string='Dataset / Dimension Name', required=True)
    target_table = fields.Char(string='Target Schema.Table', required=True)
    extraction_query = fields.Text(string='Source Query / Logic (Odoo side)')
    
    last_run = fields.Datetime(string='Last Run', tracking=True)
    status = fields.Selection([
        ('idle', 'Idle'),
        ('running', 'Running'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ], string='Status', default='idle', tracking=True)
    
    last_error = fields.Text(string='Last Error Message', tracking=True)
    records_synced = fields.Integer(string='Records Synced Last Run')
    
    is_active = fields.Boolean(string='Active', default=True)

    def action_run_sync(self):
        for job in self:
            job.status = 'running'
            # In a real environment, this connects to the external Postgres reporting DB
            # e.g., using psycopg2, and pushes the data from `extraction_query`
            # For sprint simulation, we log the extraction event.
            try:
                _logger.info(f"Extracting data for {job.name} into {job.target_table}")
                # Simulate extraction
                job.write({
                    'last_run': fields.Datetime.now(),
                    'status': 'success',
                    'records_synced': 100, # Simulated
                    'last_error': False,
                })
            except Exception as e:
                job.write({
                    'last_run': fields.Datetime.now(),
                    'status': 'failed',
                    'last_error': str(e),
                })

    @api.model
    def run_all_active_jobs(self):
        jobs = self.search([('is_active', '=', True)])
        for job in jobs:
            job.action_run_sync()

class LhiDataQualityCheck(models.Model):
    _name = 'lhi.data.quality.check'
    _description = 'Reporting Data Quality Check'
    _inherit = ['mail.thread']

    name = fields.Char(string='Check Rule Name', required=True)
    job_id = fields.Many2one('lhi.reporting.job', string='Related Sync Job')
    
    check_query = fields.Text(string='Validation Query (SQL/ORM)', required=True)
    expected_result = fields.Char(string='Expected Result')
    
    last_run = fields.Datetime(string='Last Evaluated')
    is_passing = fields.Boolean(string='Passing?', default=True, tracking=True)
    
    def action_evaluate(self):
        for check in self:
            # Simulate check
            _logger.info(f"Running DQC: {check.name}")
            check.write({
                'last_run': fields.Datetime.now(),
                'is_passing': True
            })
