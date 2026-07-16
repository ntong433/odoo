# -*- coding: utf-8 -*-
{
    'name': 'LHI Feature Flag Controller',
    'version': '19.0.1.0.0',
    'category': 'Extra Tools',
    'summary': 'Feature gate system for Accounting cutover and beta modules',
    'description': """
Enforces feature gates and controls system-wide feature flags,
specifically protecting the new LHI Accounting capability until formal sign-off.
""",
    'author': 'Life Helpers Initiative',
    'website': 'https://www.lhinigeria.org',
    'license': 'LGPL-3',
    'depends': ['lhi_base', 'lhi_audit'],
    'data': [
        'security/ir.model.access.csv',
        'views/feature_control_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
