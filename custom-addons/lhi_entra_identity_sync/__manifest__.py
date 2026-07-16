{
    "name": "LHI Entra Identity Sync",
    "version": "19.0.1.0.0",
    "category": "Technical Settings",
    "summary": "Entra identity, manager, and existing-group synchronization",
    "description": """
Microsoft Entra identity synchronization for LHI ERP.

Entra supplies organizational identity, reporting lines, account state, and approved
functional memberships. Existing Odoo groups, record rules, project assignments,
approval matrices, segregation-of-duties rules, and protected administrators remain
the authoritative authorization controls.
""",
    "author": "Life Helpers Initiative",
    "website": "https://www.lhinigeria.org",
    "license": "LGPL-3",
    "depends": [
        "hr",
        "auth_oauth",
        "lhi_microsoft_graph_core",
        "lhi_approval_matrix",
    ],
    "data": [
        "security/lhi_entra_identity_security.xml",
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/entra_group_mapping_views.xml",
        "views/entra_configuration_views.xml",
        "views/entra_sync_run_views.xml",
        "views/res_users_views.xml",
        "views/hr_employee_views.xml",
        "views/res_groups_views.xml",
        "views/approval_matrix_views.xml",
        "views/lhi_entra_identity_menus.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
