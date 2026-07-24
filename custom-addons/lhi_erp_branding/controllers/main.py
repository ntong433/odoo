# -*- coding: utf-8 -*-
import mimetypes

from odoo import http
from odoo.addons.web.controllers.webmanifest import WebManifest
from odoo.http import request
from odoo.tools import file_open


class LHIWebManifest(WebManifest):

    def _get_webmanifest(self):
        manifest_data = super()._get_webmanifest()
        manifest_data['name'] = 'LHI ERP'
        manifest_data['short_name'] = 'LHI ERP'
        manifest_data['icons'] = [
            {
                'src': '/lhi_erp_branding/static/src/img/lhi_icon_192.png?v=lhi_19_0',
                'sizes': '192x192',
                'type': 'image/png',
            },
            {
                'src': '/lhi_erp_branding/static/src/img/lhi_icon_512.png?v=lhi_19_0',
                'sizes': '512x512',
                'type': 'image/png',
            },
        ]
        return manifest_data

    def _icon_path(self):
        return 'lhi_erp_branding/static/src/img/lhi_icon_192.png'

    @http.route(
        ['/favicon.ico', '/web/static/img/favicon.ico'],
        type='http',
        auth='public',
        readonly=True,
    )
    def favicon(self, **kwargs):
        icon_relative_path = 'lhi_erp_branding/static/src/img/lhi_favicon.ico'
        with file_open(icon_relative_path, 'rb') as favicon_file:
            favicon_bytes = favicon_file.read()
        mime_type = mimetypes.guess_type(icon_relative_path)[0] or 'image/x-icon'
        return request.make_response(
            favicon_bytes,
            headers=[
                ('Content-Type', mime_type),
                ('Cache-Control', 'public, max-age=86400'),
            ],
        )
