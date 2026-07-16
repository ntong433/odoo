{
    "name": "LHI Document Workspace",
    "version": "19.0.1.0.0",
    "category": "Productivity/Documents",
    "summary": "Permission-aware Odoo workspaces for SharePoint business documents",
    "description": """
Provides scoped native Odoo document workspaces backed by SharePoint Online.
Users preview documents in Odoo and open Office documents in Microsoft 365
without introducing a second authorization engine or anonymous sharing links.
""",
    "author": "Life Helpers Initiative",
    "website": "https://work.lhinigeria.org",
    "license": "LGPL-3",
    "depends": [
        "lhi_web_shell",
        "lhi_sharepoint_storage",
        "lhi_funding_opportunity",
        "lhi_proposal_management",
        "lhi_grant_award",
        "lhi_project_workplan",
        "lhi_meal",
        "lhi_project_reporting",
        "lhi_partner_management",
        "lhi_purchase_request",
        "lhi_procurement",
        "lhi_purchase_order",
        "lhi_inventory",
        "lhi_asset_management",
        "lhi_fleet_operations",
        "lhi_project_compliance",
        "lhi_project_closeout",
    ],
    "data": [
        "security/lhi_document_workspace_security.xml",
        "security/ir.model.access.csv",
        "data/storage_policy_data.xml",
        "views/document_template_views.xml",
        "views/document_item_views.xml",
        "views/storage_policy_views.xml",
        "views/document_workspace_views.xml",
        "views/lhi_document_workspace_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "lhi_document_workspace/static/src/js/document_workspace.js",
            "lhi_document_workspace/static/src/xml/document_workspace.xml",
            "lhi_document_workspace/static/src/scss/document_workspace.scss",
        ],
        "web.assets_unit_tests": [
            # Existing LHI web-shell/dashboard tests still import Odoo's legacy
            # helper aliases. Keep those test-only helpers available so the
            # shared Hoot bundle can dry-run all installed test modules.
            "web/static/lib/qunit/qunit-2.9.1.js",
            "web/static/tests/legacy/helpers/**/*.js",
            "lhi_document_workspace/static/tests/document_workspace.test.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
