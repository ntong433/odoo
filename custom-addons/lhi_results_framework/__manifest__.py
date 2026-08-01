# -*- coding: utf-8 -*-
{
    'name': 'LHI Results Framework',
    'version': '19.0.2.0.0',
    'category': 'Project MEAL',
    'summary': 'Programme Results Framework and Indicators',
    'depends': ['lhi_base', 'lhi_security', 'lhi_project_lifecycle', 'lhi_project_workplan', 'lhi_web_shell', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/lhi_results_framework_security.xml',
        'views/lhi_results_framework_views.xml',
        'views/lhi_indicator_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
