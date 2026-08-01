# -*- coding: utf-8 -*-
{
    'name': 'LHI Vendor Management',
    'version': '19.0.2.0.0',
    'category': 'Procurement',
    'summary': 'Vendor Onboarding, Due Diligence, and Expiry Alerts',
    'depends': ['lhi_base', 'lhi_security', 'mail', 'lhi_purchase_request', 'lhi_sharepoint_storage'],
    'data': [
        'security/ir.model.access.csv',
        'security/lhi_vendor_security.xml',
        'data/ir_cron_data.xml',
        'views/lhi_vendor_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
