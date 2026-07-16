# -*- coding: utf-8 -*-
{
    'name': 'LHI Project Lifecycle',
    'version': '19.0.1.0.0',
    'category': 'Project Management',
    'summary': 'Link LHI projects with standard Odoo Project app',
    'depends': ['lhi_base', 'lhi_project_compliance', 'project'],
    'data': [
        'views/lhi_project_extension_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
