# -*- coding: utf-8 -*-
{
    'name': 'LHI Accounting Base & Feature Gate',
    'version': '19.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Preparation of LHI Accounting structures behind a strict production feature gate.',
    'depends': ['account', 'lhi_base'],
    'data': [
        'security/ir.model.access.csv',
        'security/lhi_accounting_security.xml',
        'data/ir_config_parameter_data.xml',
        'views/res_config_settings_views.xml',
        'views/menu_overrides.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
