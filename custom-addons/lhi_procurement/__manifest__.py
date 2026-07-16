# -*- coding: utf-8 -*-
{
    'name': 'LHI Procurement',
    'version': '19.0.1.0.0',
    'category': 'Procurement',
    'summary': 'RFQs, Tenders, Bid Analysis, and Recommendations',
    'depends': ['lhi_purchase_request', 'lhi_vendor_management', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/lhi_procurement_security.xml',
        'data/ir_sequence_data.xml',
        'views/lhi_procurement_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
