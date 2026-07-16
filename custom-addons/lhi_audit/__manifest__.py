# -*- coding: utf-8 -*-
{
    'name': 'LHI Audit Logging',
    'version': '19.0.1.0.0',
    'category': 'Extra Tools',
    'summary': 'Immutable and structured audit logs for LHI ERP operations',
    'description': """
Comprehensive logging and system event audits for LHI Nigeria.
Tracks critical updates, configuration edits, approvals, and authorization failures.
""",
    'author': 'Life Helpers Initiative',
    'website': 'https://www.lhinigeria.org',
    'license': 'LGPL-3',
    'depends': ['lhi_base', 'lhi_security'],
    'data': [
        'security/ir.model.access.csv',
        'views/audit_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
