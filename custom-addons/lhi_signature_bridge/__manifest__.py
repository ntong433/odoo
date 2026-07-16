# -*- coding: utf-8 -*-
{
    'name': 'LHI Signature Bridge',
    'version': '19.0.1.0.0',
    'category': 'Integration',
    'summary': 'OpenSign Bridge for Signature and Document Locking',
    'depends': ['lhi_purchase_order', 'mail', 'lhi_sharepoint_storage'],
    'data': [
        'security/ir.model.access.csv',
        'report/lhi_purchase_order_report.xml',
        'views/lhi_signature_bridge_views.xml',
        'views/lhi_purchase_order_signature_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
