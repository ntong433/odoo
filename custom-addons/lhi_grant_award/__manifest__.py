# -*- coding: utf-8 -*-
{
    'name': 'LHI Grant Award',
    'version': '19.0.1.0.0',
    'category': 'Project Management',
    'summary': 'Grant award setup and restrictions',
    'depends': ['lhi_base', 'mail', 'lhi_donor_management', 'lhi_sharepoint_storage'],
    'data': [
        'views/lhi_award_extension_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
