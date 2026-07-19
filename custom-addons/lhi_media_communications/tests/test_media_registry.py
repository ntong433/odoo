from odoo.tests.common import TransactionCase


class TestMediaRegistry(TransactionCase):

    def test_all_relational_comodels_are_registered(self):
        media_models = (
            'lhi.media.request',
            'lhi.media.activity',
            'lhi.media.success.story',
            'lhi.media.asset',
        )
        for model_name in media_models:
            model = self.env[model_name]
            for field in model._fields.values():
                if field.type in ('many2one', 'one2many', 'many2many'):
                    self.assertIn(
                        field.comodel_name,
                        self.env,
                        f'{model_name}.{field.name} has unknown comodel {field.comodel_name}',
                    )

    def test_award_relations_use_canonical_model(self):
        expected = {
            ('lhi.media.request', 'grant_id'),
            ('lhi.media.activity', 'grant_id'),
            ('lhi.media.success.story', 'grant_id'),
            ('lhi.media.asset', 'donor_id'),
        }
        for model_name, field_name in expected:
            self.assertEqual(self.env[model_name]._fields[field_name].comodel_name, 'lhi.award')

    def test_media_root_action_resolves(self):
        menu = self.env.ref('lhi_media_communications.menu_lhi_media_root')
        action = self.env.ref('lhi_media_communications.action_lhi_media_request')
        self.assertEqual(menu.action, action)
