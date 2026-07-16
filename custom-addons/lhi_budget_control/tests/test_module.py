from odoo.tests.common import TransactionCase

class TestLhiBudgetControl(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        
    def test_budget_available(self):
        plan = self.env['account.analytic.plan'].create({'name': 'Test Plan'})
        analytic = self.env['account.analytic.account'].create({'name': 'Project X', 'plan_id': plan.id})
        budget = self.env['lhi.budget'].create({
            'name': 'B2026',
            'analytic_account_id': analytic.id,
            'date_from': '2026-01-01',
            'date_to': '2026-12-31'
        })
        acc = self.env['account.account'].create({
            'name': 'Test Acc',
            'code': '99999',
            'account_type': 'expense'
        })
        line = self.env['lhi.budget.line'].create({
            'budget_id': budget.id,
            'general_account_id': acc.id,
            'planned_amount': 1000
        })
        self.assertEqual(line.available_amount, 1000)
