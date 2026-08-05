{
    "name": "LHI Memo Integration",
    "version": "19.0.2.1.9",
    "category": "Productivity",
    "summary": "Dedicated orchestration, saga operation tracking, preflight validation, and versioned contracts for Memo workflows",
    "description": """
LHI Memo Integration Orchestration
===================================
Provides a contract-isolated, idempotent saga orchestration layer for LHI Memo operations.
Exposes durable operation tracking (lhi.memo.integration.operation), preflight validation,
and versioned service contracts across SharePoint, LHI Sign, approval matrices, and Entra identity.
""",
    "author": "Life Helpers Initiative",
    "website": "https://www.lhinigeria.org",
    "license": "LGPL-3",
    "depends": [
        "lhi_memo_management",
        "lhi_approval_matrix",
        "lhi_sharepoint_storage",
        "lhi_signature_bridge",
        "lhi_entra_identity_sync",
        "lhi_audit",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/memo_integration_operation_views.xml",
        "views/memo_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
