# -*- coding: utf-8 -*-
{
    'name': 'LHI Base ERP Integration',
    'version': '19.0.1.1.1',
    'category': 'Operations',
    'summary': 'Core configuration and models for LHI Nigeria ERP system',
    'description': """
Core module for Life Helpers Initiative (LHI) Nigeria.
Defines foundational models, common partner data, and organizational structures.
""",
    'author': 'Life Helpers Initiative',
    'website': 'https://www.lhinigeria.org',
    'license': 'LGPL-3',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/menus.xml',
        'views/lhi_master_data_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
