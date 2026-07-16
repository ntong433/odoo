# -*- coding: utf-8 -*-
{
    'name': 'LHI Procurement Commitment',
    'version': '19.0.1.0.0',
    'category': 'Procurement',
    'summary': 'Operational Budget Commitments for Purchase Requests',
    'depends': ['lhi_purchase_request', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/lhi_procurement_commitment_security.xml',
        'views/lhi_procurement_commitment_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
