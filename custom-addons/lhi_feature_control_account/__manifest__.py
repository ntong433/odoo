# -*- coding: utf-8 -*-
{
    'name': 'LHI Feature Control - Accounting Bridge',
    'version': '19.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Bridges LHI feature gates with standard Odoo accounting models',
    'description': """
Auto-installable bridge module that hooks into Odoo core Accounting models
(account.move, account.payment, account.journal) to enforce the LHI Accounting feature gate.
""",
    'author': 'Life Helpers Initiative',
    'website': 'https://www.lhinigeria.org',
    'license': 'LGPL-3',
    'depends': ['lhi_feature_control', 'account'],
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': True,
}
