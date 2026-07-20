{
    "name": "LHI Programs and Procurement Integration",
    "depends": [
        "lhi_programme_management",
        "lhi_purchase_request",
    ],
    "auto_install": True,
    "installable": True,
    "application": False,
    "data": [
        "views/procurement_programme_views.xml",
        "views/project_context_bridge_views.xml",
    ],
}
