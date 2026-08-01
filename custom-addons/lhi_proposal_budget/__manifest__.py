# -*- coding: utf-8 -*-
{
    'name': 'Lhi Proposal Budget & Submission',
    'version': '19.0.2.0.0',
    'category': 'Sales/CRM',
    'summary': 'Proposal budgeting, submissions, and award conversion',
    'depends': ['lhi_proposal_management', 'lhi_base', 'lhi_security', 'mail', 'lhi_sharepoint_storage'],
    'data': [
        'security/ir.model.access.csv',
        'security/lhi_proposal_budget_security.xml',
        'wizard/lhi_award_wizard_views.xml',
        'views/lhi_proposal_budget_views.xml',
        'views/lhi_proposal_submission_views.xml',
        'views/lhi_proposal_workspace_extension.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
