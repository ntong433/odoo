# -*- coding: utf-8 -*-
{
    'name': 'LHI Asset Management',
    'version': '19.0.1.0.1',
    'category': 'Operations',
    'summary': 'Operational Asset Register and Lifecycle Management',
    'depends': ['mail', 'lhi_base', 'lhi_purchase_order', 'lhi_approval_matrix', 'lhi_web_shell'],
    'data': [
        'security/ir.model.access.csv',
        'security/lhi_asset_security.xml',
        'data/ir_sequence_data.xml',
        'views/lhi_asset_views.xml',
        'views/lhi_asset_transfer_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
