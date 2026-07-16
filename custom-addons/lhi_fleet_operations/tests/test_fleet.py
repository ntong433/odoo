from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError

class TestFleetOperations(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        
        cls.brand = cls.env['fleet.vehicle.model.brand'].create({'name': 'Toyota'})
        cls.model = cls.env['fleet.vehicle.model'].create({'name': 'Hilux', 'brand_id': cls.brand.id})
        
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'model_id': cls.model.id,
            'license_plate': 'LHI-01',
        })
        
    def test_trip_lifecycle(self):
        trip = self.env['lhi.fleet.trip'].create({
            'purpose': 'Field Visit',
            'location_from': 'HQ',
            'location_to': 'Site A',
            'date_start': '2026-08-01 08:00:00',
            'date_end': '2026-08-01 18:00:00',
            'vehicle_id': self.vehicle.id,
        })
        
        self.assertEqual(trip.state, 'draft')
        trip.action_submit()
        self.assertEqual(trip.state, 'submitted')
        
        trip.action_approve()
        self.assertEqual(trip.state, 'approved')
        
        trip.action_start()
        self.assertEqual(trip.state, 'in_progress')
        
        trip.action_done()
        self.assertEqual(trip.state, 'done')
        
    def test_incident_reporting(self):
        incident = self.env['lhi.fleet.incident'].create({
            'vehicle_id': self.vehicle.id,
            'incident_type': 'accident',
            'description': 'Minor fender bender'
        })
        
        self.assertEqual(incident.state, 'draft')
        incident.action_report()
        self.assertEqual(incident.state, 'reported')
        
        incident.action_investigate()
        self.assertEqual(incident.state, 'investigating')
        
        incident.action_resolve()
        self.assertEqual(incident.state, 'resolved')
