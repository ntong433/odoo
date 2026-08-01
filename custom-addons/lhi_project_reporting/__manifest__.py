# -*- coding: utf-8 -*-
{
    'name': 'LHI Project Reporting',
    'version': '19.0.2.0.0',
    'category': 'Project Management',
    'summary': 'Project Reporting Workflows',
    'depends': ['lhi_base', 'lhi_security', 'lhi_project_lifecycle', 'mail', 'lhi_sharepoint_storage'],
    'data': [
        'security/ir.model.access.csv',
        'security/lhi_project_reporting_security.xml',
        'views/lhi_project_report_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
