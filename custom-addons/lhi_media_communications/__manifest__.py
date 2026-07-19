# -*- coding: utf-8 -*-
{
    'name': 'Media & Communications',
    'version': '19.0.1.0.3',
    'category': 'Media & Communications',
    'summary': 'LHI Media & Communications unit module',
    'depends': [
        'base',
        'mail',
        'project',
        'hr',
        'lhi_base',
        'lhi_project_workplan',
    ],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'data/media_sequence.xml',
        'views/media_request_views.xml',
        'views/media_activity_views.xml',
        'views/media_success_story_views.xml',
        'views/media_asset_views.xml',
        'views/project_extension_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
