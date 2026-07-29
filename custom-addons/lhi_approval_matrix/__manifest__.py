# -*- coding: utf-8 -*-
{
    'name': 'LHI Approval Matrix',
    'version': '19.0.1.1.0',
    'category': 'Operations',
    'summary': 'Multi-step approval matrix engine for LHI business workflows',
    'description': """
Approval matrix engine for LHI Nigeria.
Manages approval flows, dynamic steps, state transitions, and signature verification.
""",
    'author': 'Life Helpers Initiative',
    'website': 'https://www.lhinigeria.org',
    'license': 'LGPL-3',
    'depends': ['lhi_base', 'lhi_security', 'lhi_audit'],
    'data': [
        'security/ir.model.access.csv',
        'views/approval_matrix_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
