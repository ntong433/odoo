# -*- coding: utf-8 -*-
{
    'name': 'LHI Donor Management',
    'version': '19.0.2.0.0',
    'category': 'Sales/CRM',
    'summary': 'Enhanced Donor Relationship Records for LHI',
    'depends': ['lhi_base', 'lhi_security', 'mail', 'contacts'],
    'data': [
        'views/lhi_donor_views.xml',
        'views/lhi_donor_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
