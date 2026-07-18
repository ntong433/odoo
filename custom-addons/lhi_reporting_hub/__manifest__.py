# -*- coding: utf-8 -*-
{
    'name': 'LHI Reporting Hub',
    'version': '19.0.1.0.1',
    'category': 'Reporting',
    'summary': 'Data extraction jobs, star-schema staging, and data quality checks for LHI Reporting',
    'depends': ['base', 'lhi_base', 'mail', 'lhi_web_shell'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/reporting_jobs_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
