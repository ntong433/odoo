{
    "name": "LHI Programs and Procurement Integration",
    "version": "19.0.1.0.1",
    "author": "LHI",
    "license": "LGPL-3",
    "depends": [
        "lhi_programme_management",
        "lhi_purchase_request",
    ],
    "auto_install": False,
    "installable": True,
    "application": False,
    "data": [
        "views/procurement_programme_views.xml",
        "views/project_context_bridge_views.xml",
    ],
}
