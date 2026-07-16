from odoo.tests.common import TransactionCase

class TestProjectRisk(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.project = cls.env['lhi.project'].create({
            'name': 'Risk Project'
        })
        cls.likelihood_high = cls.env['lhi.risk.likelihood'].create({
            'name': 'High Likelihood',
            'value': 4
        })
        cls.impact_severe = cls.env['lhi.risk.impact'].create({
            'name': 'Severe Impact',
            'value': 5
        })

    def test_risk_scoring(self):
        risk = self.env['lhi.project.risk'].create({
            'name': 'Security Threat',
            'project_id': self.project.id,
            'owner_id': self.env.user.id,
            'inherent_likelihood_id': self.likelihood_high.id,
            'inherent_impact_id': self.impact_severe.id
        })
        
        # 4 * 5 = 20
        self.assertEqual(risk.inherent_score, 20)
        
        # State transitions
        self.assertEqual(risk.state, 'draft')
        risk.action_activate()
        self.assertEqual(risk.state, 'active')
        risk.action_escalate()
        self.assertEqual(risk.state, 'escalated')
        risk.action_close()
        self.assertEqual(risk.state, 'closed')
