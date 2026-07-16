# -*- coding: utf-8 -*-
from odoo import models, fields

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    lhi_entra_object_id = fields.Char(
        string="Entra Object ID", 
        related="user_id.lhi_entra_object_id", 
        store=True,
        readonly=True,
        groups="hr.group_hr_user,lhi_security.group_lhi_erp_admin",
        help="The unique identifier for this employee in Microsoft Entra ID."
    )
    
    # We will also use standard fields:
    # name, job_title, department_id, parent_id (manager), work_phone, work_email
