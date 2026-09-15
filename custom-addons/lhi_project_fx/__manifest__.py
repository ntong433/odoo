{
    "name": "LHI Project FX & Award Amendments",
    "version": "19.0.1.0.0",
    "summary": "Award amendments, donor currency and current NGN project valuation",
    "category": "LHI/Programs and Grants",
    "author": "Life Helpers Initiative Nigeria",
    "license": "LGPL-3",
    "depends": [
        "mail",
        "lhi_base",
        "lhi_security",
        "lhi_grant_award",
        "lhi_programme_management",
        "lhi_project_dashboard",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/project_fx_security.xml",
        "data/sequence.xml",
        "views/project_fx_views.xml",
    ],
    "installable": True,
    "application": False,
}
