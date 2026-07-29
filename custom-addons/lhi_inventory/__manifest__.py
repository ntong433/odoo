# -*- coding: utf-8 -*-
{
    'name': 'LHI Inventory Management',
    'version': '19.0.1.1.0',
    'category': 'Inventory',
    'summary': 'Configure operational inventory with donor/project tracking',
    'depends': ['stock', 'lhi_base', 'lhi_project_workplan'],
    'data': [
        'security/ir.model.access.csv',
        'security/lhi_inventory_security.xml',
        'views/lhi_stock_move_views.xml',
        'views/lhi_stock_quant_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
