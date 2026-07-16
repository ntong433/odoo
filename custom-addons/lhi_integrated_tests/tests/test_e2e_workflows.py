from odoo.tests.common import TransactionCase

class TestE2EWorkflows(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        
    def test_opportunity_to_procurement(self):
        # 1. Opportunity / Proposal
        donor = self.env['res.partner'].create({'name': 'Global Fund', 'is_company': True})
        proposal = self.env['lhi.proposal'].create({
            'name': 'Malaria Eradication 2026',
            'donor_id': donor.id,
            'amount_requested': 500000
        })
        proposal.action_submit()
        proposal.action_award()
        
        # 2. Project Workplan & Activity
        project = self.env['project.project'].create({'name': 'GF Malaria'})
        activity = self.env['lhi.workplan.activity'].create({
            'name': 'Procure Nets',
            'project_id': project.id
        })
        
        # 3. Procurement
        pr = self.env['lhi.purchase.request'].create({
            'name': 'PR-NETS-001',
            'project_id': project.id,
            'activity_id': activity.id,
        })
        self.env['lhi.purchase.request.line'].create({
            'request_id': pr.id,
            'description': 'Mosquito Nets',
            'quantity': 1000,
            'estimated_cost': 5000
        })
        pr.action_submit()
        
        # 4. Fleet trip for delivery (stub)
        trip = self.env['lhi.fleet.trip'].create({
            'name': 'Delivery to field',
            'project_id': project.id,
        })
        
        self.assertEqual(proposal.state, 'awarded')
        self.assertEqual(pr.state, 'submitted')
        self.assertEqual(trip.state, 'draft')
