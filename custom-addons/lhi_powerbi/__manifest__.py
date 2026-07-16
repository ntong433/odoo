# -*- coding: utf-8 -*-
{
    'name': 'LHI Power BI Embedded',
    'version': '19.0.1.0.0',
    'category': 'Reporting',
    'summary': 'Registry and Owl viewer for embedded Power BI reports with RLS mapping',
    'depends': ['base', 'lhi_base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/powerbi_report_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'lhi_powerbi/static/src/components/**/*',
            'lhi_powerbi/static/src/xml/**/*',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
