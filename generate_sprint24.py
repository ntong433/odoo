import os

modules = [
    {
        'name': 'lhi_ng_hr_payroll',
        'title': 'LHI Nigerian Payroll Sandbox',
        'depends': ['account', 'hr', 'lhi_base', 'lhi_accounting_base'],
    },
    {
        'name': 'lhi_ng_edi',
        'title': 'LHI NRS E-Invoicing Adapter',
        'depends': ['account', 'lhi_base', 'lhi_accounting_base'],
    },
    {
        'name': 'lhi_migration_tooling',
        'title': 'LHI Accounting Migration Tooling',
        'depends': ['account', 'lhi_base', 'lhi_accounting_base'],
    }
]

for mod in modules:
    base = f"custom-addons/{mod['name']}"
    os.makedirs(f"{base}/models", exist_ok=True)
    os.makedirs(f"{base}/views", exist_ok=True)
    os.makedirs(f"{base}/security", exist_ok=True)
    os.makedirs(f"{base}/tests", exist_ok=True)
    os.makedirs(f"{base}/data", exist_ok=True)
    
    manifest_content = f"""# -*- coding: utf-8 -*-
{{
    'name': '{mod['title']}',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations',
    'depends': {mod['depends']},
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}}
"""
    with open(f"{base}/__manifest__.py", "w") as f:
        f.write(manifest_content)
        
    with open(f"{base}/__init__.py", "w") as f:
        f.write("from . import models\n")
        
    with open(f"{base}/models/__init__.py", "w") as f:
        f.write("from . import models\n")
        
    with open(f"{base}/tests/__init__.py", "w") as f:
        f.write("from . import test_module\n")

    # Creating empty or basic files
    with open(f"{base}/security/ir.model.access.csv", "w") as f:
        f.write("id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink\n")
        
    with open(f"{base}/views/views.xml", "w") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n<odoo>\n</odoo>\n')
        
    test_content = f"""from odoo.tests.common import TransactionCase

class Test{mod['name'].replace('_', ' ').title().replace(' ', '')}(TransactionCase):
    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))
"""
    with open(f"{base}/tests/test_module.py", "w") as f:
        f.write(test_content)
