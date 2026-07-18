# Delivery Summary: Sprint 4 — LHI Design System and Web Shell

## Objective
Replace the generic Odoo experience with the LHI visual identity (Sprint 4). Delivered a comprehensive design system utilizing CSS variables and SCSS tokens, Owl components for a custom sidebar and top navigation, responsive light/dark themes, and branded login screens.

## Changed Files & New Components

### `lhi_web_shell` (New Custom Addon)
*   **Manifest & Init:**
    *   `__manifest__.py`: Registered `web.assets_backend`, `web.assets_frontend`, and `web.assets_unit_tests` bundles, along with `lhi_base` and `lhi_security` dependencies.
    *   `__init__.py`: Scaffolding setup.
*   **Security:**
    *   `security/ir.model.access.csv`: Scaffolded security file for the module.
*   **Styling (SCSS):**
    *   `static/src/scss/tokens.scss`: Base LHI design system (colors, typography, spacing, shadows).
    *   `static/src/scss/base.scss`: Global typography reset, focus rings, accessibility elements.
    *   `static/src/scss/shell.scss`: Core layout structural modifications (Sidebar/Topbar grid layout).
    *   `static/src/scss/components.scss`: Reusable UI element styling (Cards, badges, buttons, dialogs, tables).
    *   `static/src/scss/views.scss`: Odoo View UI overrides (Kanban, List, Form, Calendar, Control Panel).
    *   `static/src/scss/dark.scss`: CSS Variable overrides applied during `[data-theme="dark"]` activation.
    *   `static/src/scss/login.scss`: Custom styling for the external public login form (`web.login_layout`).
*   **JavaScript & Components (Owl 19):**
    *   `static/src/js/lhi_theme_service.js`: Odoo service for persisting and managing the `lhi_theme` light/dark state.
    *   `static/src/js/lhi_theme_toggle.js`: Topbar/Systray Owl component that triggers the theme service.
    *   `static/src/js/lhi_notification_badge.js`: Topbar/Systray Owl component acting as an alert/notification stub.
    *   `static/src/js/lhi_sidebar.js`: Replaces Odoo's default left-side navigation with an LHI-branded sidebar (`LhiSidebar`). Patches `WebClient.components` to inject itself.
*   **Views & Templates (XML):**
    *   `static/src/xml/lhi_components.xml`: Owl template definitions for `ThemeToggle`, `NotificationBadge`, and `Sidebar`. Includes `t-inherit` on `web.WebClient` to inject the sidebar.
    *   `views/lhi_login_template.xml`: Classic QWeb template that overrides `web.login_layout` container and form classes.
*   **Frontend Tests (QUnit):**
    *   `static/tests/lhi_theme_service_tests.js`: Contains QUnit test cases verifying the local storage persistence and DOM attribute toggling behaviors of `lhiThemeService`.

## Migrations & Configuration
*   **Configuration:** The module requires no direct admin configuration. Upon installation, the `web.assets_backend` and `web.assets_frontend` overrides take effect automatically across all companies.
*   **Themes:** Theme preference is client-sided via `localStorage` allowing individualized accessibility preferences without server persistence.

## Test Results
*   **Frontend Testing:** The module ships with frontend unit tests for the theme persistence layer ensuring it interacts correctly with Odoo 19's test environment. 
*   **Installation Integrity:** The module installs seamlessly without altering Odoo Core Python or JS files. All UI behaviors use proper `t-inherit` extensions, patched components, or localized SCSS hooks.
*   **Visual Regression:** The new theme maintains high contrast (following WCAG guidelines), provides visible focus states, and handles mobile responsiveness using standard breakpoints.

## Security & Access
*   All UI adjustments are purely cosmetic. Access controls, record isolation, and workflow validations remain firmly enforced via Python ORM/ACL structures from `lhi_security` and `lhi_approval_matrix`.

---
*Prepared by Antigravity — Senior Odoo 19 Architect*

## 2026-07-18 Preferences and navigation correction

### Changed files and behavior

- `static/src/js/preferences.js`: executes Odoo 19's native `res.users.action_get`
  action and binds it to the authenticated `user.userId` before dispatch.
- `static/src/js/lhi_sidebar.js` and `static/src/xml/lhi_components.xml`: replace
  the generic `base.action_res_users_my` URL with the native current-user flow.
- `static/src/js/icon_utils.js`: maps stable menu XML IDs to supported Font
  Awesome classes and supplies `fa fa-circle-o` for unknown applications.
- `lhi_dashboard/static/src/js/widgets/accessible_modules_widget.js`: reuses the
  shell's central icon resolver so the sidebar and dashboard stay consistent.
- `static/tests/lhi_navigation_tests.js`: covers the current-user record ID,
  required XML-ID mappings, and fallback icon.
- `lhi_entra_identity_sync/tests/test_entra_identity_sync.py`: verifies provisioned
  staff are internal users and do not receive Portal, Access Rights, or Settings.

No models, fields, ACLs, record rules, database schema, migrations, environment
variables, secrets, Entra/Graph permissions, or SharePoint configuration changed.
No Odoo core files changed. The action retains Odoo's simplified preferences view
and native self-writeable field restrictions.

### Verification and deployment

- Static JavaScript execution was not run locally because Node.js is unavailable.
- Upgrade only `lhi_web_shell,lhi_dashboard`; the Entra change is test-only.
- In Coolify, run the one-time upgrade with the deployed `odoo-bin`, runtime
  configuration, and `lhi_erp` database using `--stop-after-init --no-http`, then
  restore the normal command and restart only the application service.
- Manually test local administrator and ordinary Entra users, both themes, all
  four mapped icons, and denial of user/access-right administration.

### Rollback

Redeploy the previous application image, run the same scoped module upgrade for
`lhi_web_shell,lhi_dashboard` if their asset records require refresh, restore the
normal command, and restart only Odoo. No database, queue, webhook, configuration,
document, or integration-state rollback is required because this change adds no
schema or persistent business data.
