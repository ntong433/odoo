# -*- coding: utf-8 -*-
{
    'name': 'LHI Integration and Identity',
    'version': '19.0.1.0.2',
    'category': 'Technical Settings',
    'summary': 'Shared organizational identity and reusable integration infrastructure',
    'description': """
LHI Integration and Identity — Sprint 6
=======================================

Deliverables:
• Entra login configuration using OAuth2.
• Employee and User identity mapping via Entra Object ID.
• Manager, department, job title, and phone synchronization via Graph API.
• Reusable models for API connections, Webhooks, Idempotency, and Retry logic.
• Integration Monitoring Dashboard.
""",
    'author': 'Life Helpers Initiative',
    'website': 'https://www.lhinigeria.org',
    'license': 'LGPL-3',
    'depends': [
        'base', 
        'auth_oauth',
        'lhi_base', 
        'lhi_security'
    ],
    'data': [
        'security/lhi_integration_security.xml',
        'security/ir.model.access.csv',
        'data/auth_oauth_data.xml',
        'data/ir_cron.xml',
        'views/res_users_views.xml',
        'views/lhi_integration_connection_views.xml',
        'views/lhi_integration_job_views.xml',
        'views/lhi_integration_webhook_views.xml',
        'views/lhi_integration_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
