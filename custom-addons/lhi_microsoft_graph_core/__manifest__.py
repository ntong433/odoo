{
    "name": "LHI Microsoft Graph Core",
    "version": "19.0.1.1.0",
    "category": "Technical Settings",
    "summary": "Secure Microsoft Graph and SharePoint connection foundation",
    "description": """
Reusable Microsoft Graph foundation for LHI ERP.

Provides client-secret application authentication, delegated user authorization,
secure token caching, bounded Graph pagination, throttling-aware retries, SharePoint
site/library validation, diagnostics, and project workspace templates.
""",
    "author": "Life Helpers Initiative",
    "website": "https://www.lhinigeria.org",
    "license": "LGPL-3",
    "depends": [
        "base_setup",
        "auth_oauth",
        "lhi_integration",
        "lhi_audit",
    ],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "security/lhi_microsoft_graph_security.xml",
        "security/ir.model.access.csv",
        "data/workspace_templates.xml",
        "data/ir_cron.xml",
        "views/lhi_graph_connection_views.xml",
        "views/lhi_graph_diagnostic_views.xml",
        "views/lhi_graph_request_log_views.xml",
        "views/lhi_graph_workspace_template_views.xml",
        "views/res_users_views.xml",
        "views/res_config_settings_views.xml",
        "views/lhi_microsoft_graph_menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
