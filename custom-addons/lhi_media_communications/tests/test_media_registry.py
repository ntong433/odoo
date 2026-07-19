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

    def test_media_privilege_labels_are_safe_for_generated_user_view(self):
        category = self.env.ref(
            'lhi_media_communications.module_category_lhi_media'
        )
        privilege = self.env.ref(
            'lhi_media_communications.res_groups_privilege_lhi_media'
        )
        self.assertEqual(category.name, 'Media and Communications')
        self.assertEqual(privilege.name, 'Media and Communications')
        self.assertEqual(privilege.category_id, category)
