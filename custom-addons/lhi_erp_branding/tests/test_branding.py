# -*- coding: utf-8 -*-
import json

from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestLHIERPBranding(HttpCase):

    def test_webmanifest_branding(self):
        """Test PWA webmanifest name, short_name, and icon branding."""
        response = self.url_open('/web/manifest.webmanifest')
        self.assertEqual(response.status_code, 200)
        manifest_json = response.json()
        self.assertEqual(manifest_json.get('name'), 'LHI ERP')
        self.assertEqual(manifest_json.get('short_name'), 'LHI ERP')
        icon_sources = [icon.get('src') for icon in manifest_json.get('icons', [])]
        self.assertTrue(any('lhi_icon_192.png' in src for src in icon_sources))

    def test_favicon_routes(self):
        """Test favicon endpoints returning 200 OK with icon content-type."""
        for route_path in ['/favicon.ico', '/web/static/img/favicon.ico', '/lhi_erp_branding/static/src/img/lhi_favicon.png']:
            response = self.url_open(route_path)
            self.assertEqual(response.status_code, 200)

    def test_system_parameter_web_app_name(self):
        """Test system parameter web.web_app_name is set to LHI ERP."""
        config_param = self.env['ir.config_parameter'].sudo().get_param('web.web_app_name')
        self.assertEqual(config_param, 'LHI ERP')

    def test_login_page_branding(self):
        """Test login page contains LHI ERP branding references."""
        response = self.url_open('/web/login')
        self.assertEqual(response.status_code, 200)
        content_text = response.text
        self.assertIn('LHI ERP', content_text)
        self.assertIn('lhi_favicon.png?v=20260724', content_text)
