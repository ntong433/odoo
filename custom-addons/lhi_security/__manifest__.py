# -*- coding: utf-8 -*-
{
    'name': 'LHI Security and Access Controls',
    'version': '19.0.1.0.1',
    'category': 'Security',
    'summary': 'Dedicated security groups and authorization rules for LHI ERP',
    'description': """
Security module for Life Helpers Initiative (LHI) Nigeria.
Defines LHI ERP business security groups, multi-company access rules,
and least-privilege model access lists.
""",
    'author': 'Life Helpers Initiative',
    'website': 'https://www.lhinigeria.org',
    'license': 'LGPL-3',
    'depends': ['lhi_base'],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'security/security_rules.xml',
        'views/res_users_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': True,
}
