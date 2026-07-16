# -*- coding: utf-8 -*-
{
    'name': 'LHI Project Closeout',
    'version': '19.0.1.0.0',
    'category': 'Project Management',
    'summary': 'Formal Project Closeout Checklists and Archive Controls',
    'depends': ['lhi_base', 'lhi_project_lifecycle', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/lhi_project_closeout_security.xml',
        'data/ir_sequence_data.xml',
        'views/lhi_project_closeout_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
