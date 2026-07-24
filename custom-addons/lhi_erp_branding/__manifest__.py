# -*- coding: utf-8 -*-
{
    "name": "LHI ERP Branding",
    "version": "19.0.1.1.0",
    "category": "LHI ERP",
    "summary": "LHI ERP browser title and favicon branding",
    "depends": [
        "web"
    ],
    "data": [
        "data/ir_config_parameter_data.xml",
        "views/branding_templates.xml"
    ],
    "assets": {
        "web.assets_backend": [
            "lhi_erp_branding/static/src/js/title_branding_service.js"
        ],
        "web.assets_frontend": [
            "lhi_erp_branding/static/src/js/title_branding_service.js"
        ]
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3"
}
