# -*- coding: utf-8 -*-
{
    'name': 'LHI Purchase Order',
    'version': '19.0.2.0.0',
    'category': 'Procurement',
    'summary': 'Purchase Orders, Goods Receipts, and Service Acceptance',
    'depends': ['lhi_procurement', 'lhi_security', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/lhi_purchase_order_security.xml',
        'data/ir_sequence_data.xml',
        'views/lhi_purchase_order_views.xml',
        'views/lhi_receipt_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
