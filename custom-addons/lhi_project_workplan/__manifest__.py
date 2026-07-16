# -*- coding: utf-8 -*-
{
    'name': 'LHI Project Workplan',
    'version': '19.0.1.0.0',
    'category': 'Project Management',
    'summary': 'Annual and periodic workplans linked to Odoo Projects',
    'depends': ['lhi_base', 'lhi_project_lifecycle', 'project', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/lhi_project_workplan_security.xml',
        'data/ir_cron_data.xml',
        'views/lhi_workplan_views.xml',
        'views/lhi_workplan_activity_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
