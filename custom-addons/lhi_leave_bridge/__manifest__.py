# -*- coding: utf-8 -*-
{
    'name': 'Lhi Leave Bridge & Unified Inbox',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Integration with external Next.js/Supabase Leave Management and Unified Approval Inbox',
    'depends': ['base', 'mail', 'hr', 'lhi_base', 'lhi_approval_matrix'],
    'data': [
        'security/ir.model.access.csv',
        'security/lhi_leave_security.xml',
        'data/ir_cron_data.xml',
        'views/res_users_views.xml',
        'views/lhi_unified_inbox_views.xml',
        'views/lhi_leave_cache_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'lhi_leave_bridge/static/src/components/**/*',
            'lhi_leave_bridge/static/src/xml/**/*',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
