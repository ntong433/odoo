# -*- coding: utf-8 -*-
{
    'name': 'LHI Role-Based Dashboard',
    'version': '19.0.1.2.2',
    'category': 'Productivity',
    'summary': 'Role-based dashboard and post-login routing for LHI ERP',
    'description': """
LHI Dashboard — Sprint 5
=========================
Make the LHI dashboard the default landing experience.

Deliverables:
• Post-login dashboard routing & deep-link preservation
• Role-based module launcher
• Widget registry for extensible dashboard components
• My Tasks, My Approvals, Notifications, Quick Actions, Announcements
• Dashboard administration (administrator controls)
• Mobile-responsive dashboard view
""",
    'author': 'Life Helpers Initiative',
    'website': 'https://www.lhinigeria.org',
    'license': 'LGPL-3',
    'depends': [
        'base', 
        'web', 
        'mail', 
        'lhi_base', 
        'lhi_security', 
        'lhi_approval_matrix',
        'lhi_purchase_request',
        'lhi_asset_management',
        'lhi_funding_opportunity',
        'lhi_media_communications',
        'lhi_meal',
        'lhi_web_shell',
        'stock',
        'fleet',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/lhi_dashboard_security.xml',
        'data/dashboard_data.xml',
        'views/lhi_announcement_views.xml',
        'views/lhi_dashboard_widget_views.xml',
        'views/dashboard_action.xml',
        'views/operations_hub_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'lhi_dashboard/static/src/scss/dashboard.scss',
            'lhi_dashboard/static/src/js/dashboard_widget_registry.js',
            'lhi_dashboard/static/src/js/widgets/accessible_modules_widget.js',
            'lhi_dashboard/static/src/js/widgets/announcements_widget.js',
            'lhi_dashboard/static/src/js/widgets/my_approvals_widget.js',
            'lhi_dashboard/static/src/js/widgets/my_tasks_widget.js',
            'lhi_dashboard/static/src/js/widgets/notifications_widget.js',
            'lhi_dashboard/static/src/js/widgets/quick_actions_widget.js',
            'lhi_dashboard/static/src/js/lhi_dashboard.js',
            'lhi_dashboard/static/src/js/dashboard_action.js',
            'lhi_dashboard/static/src/js/operations_hub.js',
            'lhi_dashboard/static/src/xml/lhi_dashboard.xml',
            'lhi_dashboard/static/src/xml/widgets.xml',
            'lhi_dashboard/static/src/xml/operations_hub.xml',
        ],
        'web.assets_unit_tests': [
            'lhi_dashboard/static/tests/dashboard_tests.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
