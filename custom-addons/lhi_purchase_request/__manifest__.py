# -*- coding: utf-8 -*-
{
    'name': 'LHI Purchase Request',
    'version': '19.0.1.0.2',
    'category': 'Procurement',
    'summary': 'Purchase Requests with Approval Routing and Validations',
    'depends': ['lhi_base', 'lhi_project_lifecycle', 'lhi_results_framework', 'lhi_approval_matrix', 'mail', 'lhi_sharepoint_storage', 'lhi_web_shell', 'lhi_budget_control'],
    'data': [
        'security/ir.model.access.csv',
        'security/lhi_purchase_request_security.xml',
        'data/ir_sequence_data.xml',
        'views/lhi_budget_line_views.xml',
        'views/lhi_purchase_request_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
