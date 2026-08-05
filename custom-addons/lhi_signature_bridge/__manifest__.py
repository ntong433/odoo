# -*- coding: utf-8 -*-
{
    "name": "LHI Signature Bridge",
    "version": "19.0.2.0.2",
    "category": "Integration",
    "summary": "OpenSign Bridge for Signature and Document Locking",
    "author": "Life Helpers Initiative",
    "website": "https://www.lhinigeria.org",
    "depends": [
        "lhi_purchase_order",
        "mail",
        "lhi_security",
        "lhi_sharepoint_storage",
        "lhi_entra_identity_sync",
    ],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "security/lhi_signature_bridge_security.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence_data.xml",
        "data/ir_cron.xml",
        "report/lhi_purchase_order_report.xml",
        "views/lhi_signature_bridge_views.xml",
        "views/lhi_purchase_order_signature_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
