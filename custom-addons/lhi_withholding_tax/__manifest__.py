# -*- coding: utf-8 -*-
{
    'name': 'LHI Withholding Tax (WHT)',
    'version': '19.0.1.0.0',
    'category': 'Accounting',
    'depends': ['account', 'lhi_base', 'lhi_accounting_base'],
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
