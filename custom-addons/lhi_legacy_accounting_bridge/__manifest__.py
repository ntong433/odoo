# -*- coding: utf-8 -*-
{
    'name': 'LHI Legacy Accounting Bridge',
    'version': '19.0.1.0.0',
    'category': 'Integration',
    'summary': 'Integration with Existing Odoo Enterprise Accounting',
    'depends': ['lhi_purchase_order', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/lhi_legacy_accounting_views.xml',
        'views/lhi_purchase_order_accounting_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
