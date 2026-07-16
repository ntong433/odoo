# -*- coding: utf-8 -*-
{
    'name': 'LHI Project Compliance',
    'version': '19.0.1.0.0',
    'category': 'Project Management',
    'summary': 'Project activation checklists and reporting calendar',
    'depends': ['lhi_base', 'mail', 'lhi_grant_award', 'lhi_sharepoint_storage'],
    'data': [
        'security/ir.model.access.csv',
        'security/lhi_project_compliance_security.xml',
        'views/lhi_reporting_calendar_views.xml',
        'views/lhi_project_activation_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
