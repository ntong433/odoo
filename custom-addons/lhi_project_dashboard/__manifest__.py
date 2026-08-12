{
    "name": "LHI Project Dashboard",
    "version": "19.0.1.0.0",
    "summary": "Configurable per-project Programs and Grants dashboard",
    "category": "LHI/Programs and Grants",
    "author": "Life Helpers Initiative",
    "license": "LGPL-3",
    "depends": [
        "web",
        "lhi_base",
        "lhi_security",
        "lhi_dashboard",
        "lhi_audit",
        "lhi_project_workplan",
        "lhi_results_framework",
        "lhi_programme_management",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/project_dashboard_metric_data.xml",
        "views/project_dashboard_views.xml",
        "views/project_dashboard_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "lhi_project_dashboard/static/src/js/project_dashboard.js",
            "lhi_project_dashboard/static/src/xml/project_dashboard.xml",
            "lhi_project_dashboard/static/src/scss/project_dashboard.scss",
        ],
    },
    "installable": True,
    "application": False,
}
