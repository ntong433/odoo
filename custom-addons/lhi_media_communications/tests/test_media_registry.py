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

    def test_media_activity_calendar_view_architecture(self):
        import xml.etree.ElementTree as ET
        view = self.env.ref('lhi_media_communications.view_lhi_media_activity_calendar')
        self.assertTrue(view.exists())
        self.assertEqual(view.model, 'lhi.media.activity')

        tree = ET.fromstring(view.arch)
        self.assertEqual(tree.tag, 'calendar')
        self.assertEqual(tree.attrib.get('date_start'), 'start_date')
        self.assertEqual(tree.attrib.get('date_stop'), 'end_date')
        self.assertEqual(tree.attrib.get('color'), 'owner_id')

        model_fields = self.env['lhi.media.activity']._fields
        self.assertIn('start_date', model_fields)
        self.assertIn('end_date', model_fields)
        self.assertIn('owner_id', model_fields)

        arch_fields = [node.attrib['name'] for node in tree.findall('field') if 'name' in node.attrib]
        for field_name in arch_fields:
            self.assertIn(field_name, model_fields, f"Field {field_name} in calendar view missing from lhi.media.activity")

    def test_media_activity_action_includes_calendar(self):
        action = self.env.ref('lhi_media_communications.action_lhi_media_activity')
        view_modes = [m.strip() for m in (action.view_mode or '').split(',')]
        self.assertIn('calendar', view_modes)

    def test_media_activity_calendar_loading_for_roles(self):
        from odoo.tests.common import new_test_user
        roles = (
            'lhi_media_communications.group_lhi_media_viewer',
            'lhi_media_communications.group_lhi_media_requester',
            'lhi_media_communications.group_lhi_media_officer',
            'lhi_media_communications.group_lhi_media_reviewer',
            'lhi_media_communications.group_lhi_media_manager',
        )
        for index, group_xmlid in enumerate(roles):
            user = new_test_user(
                self.env,
                login=f'test_media_cal_user_{index}',
                groups=f'base.group_user,{group_xmlid}',
            )
            # Verify view loading succeeds without AccessError or ParseError or Insufficient fields error
            views = self.env['lhi.media.activity'].with_user(user).get_views([(False, 'calendar')])
            self.assertIn('calendar', views.get('views', {}))
            self.assertEqual(views['views']['calendar']['arch']['tag'], 'calendar')

