# -*- coding: utf-8 -*-
{
    'name': 'LHI Funding Opportunity Pipeline',
    'version': '19.0.1.0.0',
    'category': 'Sales/CRM',
    'summary': 'Manage funding opportunities and go/no-go decisions',
    'depends': ['lhi_donor_management', 'lhi_base', 'mail', 'lhi_approval_matrix'],
    'data': [
        'security/lhi_funding_security.xml',
        'security/ir.model.access.csv',
        'data/lhi_funding_stage_data.xml',
        'data/lhi_funding_cron.xml',
        'views/lhi_funding_stage_views.xml',
        'views/lhi_funding_opportunity_views.xml',
        'views/lhi_funding_menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
