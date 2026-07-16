# -*- coding: utf-8 -*-
{
    'name': 'LHI Document Migration',
    'version': '19.0.1.0.0',
    'category': 'Document Management',
    'summary': 'Migrate local Odoo attachments to SharePoint safely',
    'depends': ['base', 'lhi_base', 'lhi_sharepoint_sync'],
    'data': [
        'security/ir.model.access.csv',
        'views/migration_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
