{
    "name": "LHI Programs and Fleet Integration",
    "depends": [
        "lhi_programme_management",
        "lhi_fleet_operations",
    ],
    "auto_install": True,
    "installable": True,
    "application": False,
    "data": [
        "views/fleet_programme_views.xml",
        "views/project_context_bridge_views.xml",
    ],
}
