# -*- coding: utf-8 -*-
{
    'name': 'LHI Web Shell',
    'version': '19.0.2.0.1',
    'category': 'Technical/UI',
    'summary': 'LHI design system, brand tokens, and web shell for the ERP',
    'description': """
LHI Web Shell — Sprint 4
=========================
Replaces the generic Odoo experience with the LHI visual identity.

Deliverables:
  • Verified LHI brand tokens (CSS variables / SCSS)
  • LHI login page override
  • Custom sidebar and top navigation
  • Light and dark themes
  • Responsive layout
  • Reusable cards, tables, badges, dialogs, and timelines
  • Styled form, list, kanban, calendar, and search views
  • Accessibility-reviewed markup (ARIA labels, skip links, focus rings)
  • Frontend (QUnit/Hoot) tests for Owl components
  • No Odoo core modifications
""",
    'author': 'Life Helpers Initiative',
    'website': 'https://www.lhinigeria.org',
    'license': 'LGPL-3',
    'depends': ['web', 'auth_oauth', 'base', 'mail', 'lhi_base', 'lhi_security'],
    'data': [
        'security/ir.model.access.csv',
        'views/apps_security.xml',
        'views/lhi_login_template.xml',
        'views/web_layout_override.xml',
    ],
    'assets': {
        # ── 1. Primary Variables (loaded earliest — before Odoo/Bootstrap SCSS) ──
        # tokens.scss MUST be here so $lhi-* variables exist for all later files.
        'web._assets_primary_variables': [
            ('prepend', 'lhi_web_shell/static/src/scss/tokens.scss'),
        ],

        # ── 2. Backend Web Assets (compiled together after primary variables) ──
        # Order: base → shell → views → components → dark mode
        'web.assets_web': [
            'lhi_web_shell/static/src/scss/base.scss',
            'lhi_web_shell/static/src/scss/shell.scss',
            'lhi_web_shell/static/src/scss/views.scss',
            'lhi_web_shell/static/src/scss/components.scss',
            'lhi_web_shell/static/src/scss/dark.scss',
            'lhi_web_shell/static/src/xml/lhi_components.xml',
        ],

        # ── 3. Backend JS + XML (Owl components — no SCSS here) ──
        'web.assets_backend': [
            'lhi_web_shell/static/src/js/lhi_theme_service.js',
            'lhi_web_shell/static/src/js/lhi_theme_toggle.js',
            'lhi_web_shell/static/src/js/icon_utils.js',
            'lhi_web_shell/static/src/js/preferences.js',
            'lhi_web_shell/static/src/js/lhi_sidebar.js',
            'lhi_web_shell/static/src/js/lhi_notification_badge.js',
        ],

        # ── 4. Frontend (public pages: login) ──
        'web.assets_frontend': [
            'lhi_web_shell/static/src/scss/login.scss',
        ],

        # ── 5. Unit tests ──
        'web.assets_unit_tests': [
            'lhi_web_shell/static/tests/lhi_theme_service_tests.js',
            'lhi_web_shell/static/tests/lhi_navigation_tests.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
