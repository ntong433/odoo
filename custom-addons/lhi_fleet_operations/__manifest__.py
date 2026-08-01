# -*- coding: utf-8 -*-
{
    'name': 'LHI Fleet Operations',
    'version': '19.0.2.0.0',
    'category': 'Operations',
    'summary': 'Fleet tracking, trip requests, and maintenance with donor/project metadata',
    'depends': ['fleet', 'lhi_base', 'lhi_security', 'lhi_project_workplan', 'lhi_approval_matrix'],
    'data': [
        'security/ir.model.access.csv',
        'security/lhi_fleet_security.xml',
        'data/ir_sequence_data.xml',
        'data/fleet_dashboard_data.xml',
        'views/lhi_fleet_vehicle_views.xml',
        'views/lhi_fleet_trip_views.xml',
        'views/lhi_fleet_incident_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
