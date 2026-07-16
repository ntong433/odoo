from odoo.tests.common import TransactionCase

class TestPartnerManagement(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.base_partner = cls.env['res.partner'].create({
            'name': 'Test NGO'
        })
        cls.project = cls.env['lhi.project'].create({
            'name': 'Partner Project'
        })

    def test_partner_profile(self):
        profile = self.env['lhi.partner.profile'].create({
            'partner_id': self.base_partner.id,
            'risk_rating': 'medium',
            'due_diligence_status': 'completed'
        })
        self.assertEqual(profile.name, 'Test NGO')
        self.assertEqual(profile.risk_rating, 'medium')
        
        subaward = self.env['lhi.subaward'].create({
            'name': 'SA-001',
            'partner_profile_id': profile.id,
            'project_id': self.project.id,
            'total_budget': 50000
        })
        self.assertEqual(subaward.state, 'draft')
        
        disbursement = self.env['lhi.subaward.disbursement'].create({
            'subaward_id': subaward.id,
            'name': 'Tranche 1',
            'amount_disbursed': 10000
        })
        self.assertEqual(disbursement.status, 'pending')
