# -*- coding: utf-8 -*-
{
    'name': 'LHI Project Risk Management',
    'version': '19.0.1.0.0',
    'category': 'Project Management',
    'summary': 'Project Risk Register and Matrix',
    'depends': ['lhi_base', 'lhi_project_lifecycle', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/lhi_project_risk_security.xml',
        'data/lhi_risk_matrix_data.xml',
        'views/lhi_project_risk_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
