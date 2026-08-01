# -*- coding: utf-8 -*-
{
    'name': 'LHI Partner Management',
    'version': '19.0.2.0.0',
    'category': 'Project Management',
    'summary': 'Partner Sub-awards, Budgets, Deliverables, and Liquidations',
    'depends': ['lhi_base', 'lhi_security', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/lhi_partner_management_security.xml',
        'views/lhi_partner_profile_views.xml',
        'views/lhi_subaward_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
