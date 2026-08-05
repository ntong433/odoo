{
    "name": "LHI SharePoint Document Storage",
    "version": "19.0.1.0.2",
    "category": "Technical Settings",
    "summary": "Policy-based SharePoint storage for LHI business documents",
    "description": """
Stores policy-approved LHI business-document bytes in SharePoint Online while
retaining Odoo metadata, business links, workflow state, and audit references.
Technical attachments remain on Odoo's standard storage backend.
""",
    "author": "Life Helpers Initiative",
    "website": "https://www.lhinigeria.org",
    "license": "LGPL-3",
    "depends": [
        "web",
        "lhi_microsoft_graph_core",
    ],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "security/lhi_sharepoint_storage_security.xml",
        "security/ir.model.access.csv",
        "data/storage_policy_data.xml",
        "data/ir_cron.xml",
        "views/document_item_views.xml",
        "views/storage_policy_views.xml",
        "views/lhi_sharepoint_storage_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "lhi_sharepoint_storage/static/src/js/sharepoint_many2many_binary.js",
            "lhi_sharepoint_storage/static/src/xml/sharepoint_many2many_binary.xml",
        ],
        "web.assets_unit_tests": [
            "lhi_sharepoint_storage/static/tests/sharepoint_upload.test.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
