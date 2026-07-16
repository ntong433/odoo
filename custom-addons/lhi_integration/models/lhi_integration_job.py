# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, timedelta

class LhiIntegrationJob(models.Model):
    _name = 'lhi.integration.job'
    _description = 'Integration Sync Job / Dead-letter Queue'
    _order = 'create_date desc'

    name = fields.Char(string="Reference", required=True, default="New Job")
    model_name = fields.Char(string="Target Model", required=True)
    record_id = fields.Integer(string="Record ID", required=True)
    action = fields.Char(string="Action to perform", required=True)
    
    state = fields.Selection([
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('done', 'Done'),
        ('failed', 'Failed'),
        ('dead_letter', 'Dead Letter')
    ], string="Status", default='pending', required=True)
    
    retry_count = fields.Integer(string="Retry Count", default=0)
    max_retries = fields.Integer(string="Max Retries", default=3)
    next_retry = fields.Datetime(string="Next Retry At")
    
    description = fields.Text(string="Job Description")
    last_error = fields.Text(string="Last Error Message")

    @api.model
    def create_job(self, model_name, record_id, action, description=""):
        return self.create({
            'name': f"{model_name} / {record_id} [{action}]",
            'model_name': model_name,
            'record_id': record_id,
            'action': action,
            'description': description
        })

    def process_jobs(self):
        """ 
        Cron-triggered function to process pending and retry jobs.
        """
        now = fields.Datetime.now()
        jobs = self.search([
            ('state', 'in', ['pending', 'failed']),
            '|', ('next_retry', '=', False), ('next_retry', '<=', now),
            ('retry_count', '<', 3)
        ], limit=50)

        for job in jobs:
            job.state = 'running'
            self.env.cr.commit() # Commit running state before executing
            try:
                # Dynamically call the action on the target record
                target_record = self.env[job.model_name].browse(job.record_id)
                if hasattr(target_record, f'action_{job.action}'):
                    getattr(target_record, f'action_{job.action}')()
                
                job.write({
                    'state': 'done',
                    'last_error': False
                })
            except Exception as e:
                job.retry_count += 1
                state = 'failed'
                if job.retry_count >= job.max_retries:
                    state = 'dead_letter'
                    
                job.write({
                    'state': state,
                    'last_error': str(e),
                    'next_retry': now + timedelta(minutes=15 * job.retry_count)
                })
            self.env.cr.commit()
