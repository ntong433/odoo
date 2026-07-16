# -*- coding: utf-8 -*-
{
    'name': 'LHI Project Issue Management',
    'version': '19.0.1.0.0',
    'category': 'Project Management',
    'summary': 'Project Issue Register and Corrective Actions',
    'depends': [
        'lhi_base',
        'lhi_project_lifecycle',
        'lhi_project_risk',
        'mail',
        'lhi_sharepoint_storage',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/lhi_project_issue_security.xml',
        'views/lhi_project_issue_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
