# -*- coding: utf-8 -*-
from odoo import models, fields

class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    lhi_project_id = fields.Many2one('lhi.project', string='Default Project', tracking=True)
    lhi_donor_id = fields.Many2one('res.partner', string='Donor Ownership', tracking=True)
    lhi_grant_id = fields.Char(string='Grant Reference', tracking=True)
    lhi_office_id = fields.Many2one('lhi.department', string='Operating Office', tracking=True) # or something similar
    lhi_custodian_id = fields.Many2one('res.users', string='Custodian / Key Holder', tracking=True)
    
    lhi_insurance_expiry = fields.Date(string='Insurance Expiry', tracking=True)
    lhi_registration_expiry = fields.Date(string='Registration Expiry', tracking=True)
    lhi_permit_expiry = fields.Date(string='Special Permit Expiry', tracking=True)

class FleetVehicleLogServices(models.Model):
    _inherit = 'fleet.vehicle.log.services'
    
    lhi_project_id = fields.Many2one('lhi.project', string='Charged Project', tracking=True)
    lhi_activity_id = fields.Many2one('lhi.workplan.activity', string='Charged Activity')
    lhi_funding_source_id = fields.Many2one('lhi.funding.source', string='Funding Source')

class FleetVehicleLogContract(models.Model):
    _inherit = 'fleet.vehicle.log.contract'
    
    lhi_donor_id = fields.Many2one('res.partner', string='Financed By Donor')

class FleetVehicleOdometer(models.Model):
    _inherit = 'fleet.vehicle.odometer'
    
    lhi_trip_id = fields.Many2one('lhi.fleet.trip', string='Related Trip')
