# -*- coding: utf-8 -*-
{
    'name': 'LHI SharePoint Sync & Scale Controls',
    'version': '19.0.1.0.0',
    'category': 'Document Management',
    'summary': 'SharePoint 5,000 threshold protection, Graph notifications, and Delta Sync',
    'depends': ['base', 'mail', 'lhi_base'],
    'data': [
        'security/ir.model.access.csv',
        'data/cron_jobs.xml',
        'views/sharepoint_partition_views.xml',
        'views/sharepoint_subscription_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
