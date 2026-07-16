# -*- coding: utf-8 -*-
{
    'name': 'LHI Web Shell',
    'version': '19.0.1.0.0',
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
    'depends': ['web', 'base', 'mail', 'lhi_base', 'lhi_security'],
    'data': [
        'security/ir.model.access.csv',
        'views/lhi_login_template.xml',
    ],
    'assets': {
        # ── Backend bundle (authenticated views) ──────────────────────────────
        'web.assets_backend': [
            # 1. Tokens / variables (must load first)
            'lhi_web_shell/static/src/scss/tokens.scss',
            # 2. Base reset & typography
            'lhi_web_shell/static/src/scss/base.scss',
            # 3. Shell layout (sidebar, topbar, breadcrumbs)
            'lhi_web_shell/static/src/scss/shell.scss',
            # 4. Component library (cards, badges, dialogs, timelines, tables)
            'lhi_web_shell/static/src/scss/components.scss',
            # 5. View overrides (form, list, kanban, calendar, search)
            'lhi_web_shell/static/src/scss/views.scss',
            # 6. Dark-mode overrides
            'lhi_web_shell/static/src/scss/dark.scss',
            # JS: theme toggle service and component
            'lhi_web_shell/static/src/js/lhi_theme_service.js',
            'lhi_web_shell/static/src/js/lhi_theme_toggle.js',
            'lhi_web_shell/static/src/js/lhi_sidebar.js',
            # JS: notification badge component
            'lhi_web_shell/static/src/js/lhi_notification_badge.js',
            # XML templates
            'lhi_web_shell/static/src/xml/lhi_components.xml',
        ],
        # ── Frontend login/public bundle ──────────────────────────────────────
        'web.assets_frontend': [
            'lhi_web_shell/static/src/scss/tokens.scss',
            'lhi_web_shell/static/src/scss/login.scss',
        ],
        # ── QUnit / Hoot tests ────────────────────────────────────────────────
        'web.assets_unit_tests': [
            'lhi_web_shell/static/tests/lhi_theme_service_tests.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
