{
    "name": "LHI Programs and Fleet Integration",
    "version": "19.0.1.0.1",
    "author": "LHI",
    "license": "LGPL-3",
    "depends": [
        "lhi_programme_management",
        "lhi_fleet_operations",
    ],
    "auto_install": False,
    "installable": True,
    "application": False,
    "data": [
        "views/fleet_programme_views.xml",
        "views/project_context_bridge_views.xml",
    ],
}
