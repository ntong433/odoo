# -*- coding: utf-8 -*-
{
    'name': 'LHI Proposal Management',
    'version': '19.0.2.0.0',
    'category': 'Sales/CRM',
    'summary': 'Manage concept notes and proposal development workspaces',
    'depends': ['lhi_funding_opportunity', 'lhi_security', 'mail', 'lhi_approval_matrix', 'lhi_sharepoint_storage'],
    'data': [
        'security/lhi_proposal_security.xml',
        'security/ir.model.access.csv',
        'data/lhi_proposal_section_template_data.xml',
        'views/lhi_proposal_views.xml',
        'views/lhi_proposal_section_views.xml',
        'views/lhi_funding_opportunity_extension.xml',
        'views/lhi_proposal_menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
