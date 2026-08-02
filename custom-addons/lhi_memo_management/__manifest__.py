{
    "name": "LHI Memo Management",
    "version": "19.0.2.0.0",
    "category": "Productivity",
    "summary": "Word, SharePoint, approval, and LHI Sign memo lifecycle",
    "description": """
LHI Memo Management
===================
Creates and governs internal memos while Microsoft Word for the web remains the
authoring surface, SharePoint Online remains the document system of record, Odoo
remains the workflow and authorization system, and LHI Sign/OpenSign remains the
electronic-signature provider.

v19.0.2.0.0 — Document Gateway
-------------------------------
All lhi.document.item access from Memo business logic is now mediated through
MemoDocumentGateway, enforcing six-step authorization before any sudo elevation.
Normal employees (lhi_employee) retain zero direct access to lhi.document.item.
""",
    "author": "Life Helpers Initiative",
    "website": "https://www.lhinigeria.org",
    "license": "LGPL-3",
    "depends": [
        "mail",
        "lhi_security",
        "lhi_base",
        "lhi_purchase_request",
        "lhi_sharepoint_sync",
        "lhi_sharepoint_storage",
        "lhi_signature_bridge",
        "lhi_entra_identity_sync",
        "lhi_approval_matrix",
        "lhi_dashboard",
    ],
    "data": [
        "security/lhi_memo_security.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence_data.xml",
        "data/storage_policy_data.xml",
        "data/memo_category_data.xml",
        "data/ir_cron.xml",
        "views/memo_category_views.xml",
        "views/memo_document_template_views.xml",
        "views/memo_views.xml",
        "views/memo_menus.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
