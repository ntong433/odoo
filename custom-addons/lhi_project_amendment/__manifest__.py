# -*- coding: utf-8 -*-
{
    'name': 'LHI Project Amendment Tracking',
    'version': '19.0.1.0.0',
    'category': 'Project Management',
    'summary': 'Project Amendment and Change Control',
    'depends': ['lhi_base', 'lhi_project_lifecycle', 'mail', 'lhi_sharepoint_storage'],
    'data': [
        'security/ir.model.access.csv',
        'security/lhi_project_amendment_security.xml',
        'data/ir_cron_data.xml',
        'views/lhi_project_amendment_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
