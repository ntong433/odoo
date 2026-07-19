# -*- coding: utf-8 -*-
{
    'name': 'LHI MEAL',
    'version': '19.0.1.1.0',
    'category': 'Project MEAL',
    'summary': 'Monitoring, Evaluation, Accountability and Learning Data Collection',
    'depends': [
        'lhi_base',
        'lhi_security',
        'lhi_project_workplan',
        'lhi_results_framework',
        'mail',
        'lhi_sharepoint_storage',
    ],
    'data': [
        'security/lhi_meal_security.xml',
        'security/ir.model.access.csv',
        'views/lhi_meal_data_views.xml',
        'views/lhi_meal_evidence_views.xml',
        'views/lhi_meal_dashboard_views.xml',
        'views/lhi_meal_initiative_views.xml',
        'views/menu_views.xml',
        'data/ir_cron_data.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
