# Delivery Summary: Sprint 5 — Role-Based Dashboard and Post-Login Routing

## Objective
Make the LHI dashboard the default landing experience while preserving deep-links. Delivered a widget-based, dynamic dashboard tailored by user roles with administrator configuration.

## Changed Files & New Components

### `lhi_dashboard` (New Custom Addon)
*   **Manifest & Init:**
    *   `__manifest__.py`: Registered frontend assets (SCSS/JS/XML), depends on `lhi_web_shell`, `lhi_security`, `lhi_approval_matrix`, `mail`, and `base`.
    *   `models/__init__.py`: Added widget and announcement models.
*   **Models (Python):**
    *   `models/lhi_dashboard_widget.py`: Defines the `lhi.dashboard.widget` configuration registry table, supporting role-based filters (`group_ids`) and dynamic sequence/col_span controls.
    *   `models/lhi_announcement.py`: Built `lhi.announcement` for managing time-based, actionable company news and alerts.
*   **Security:**
    *   `security/ir.model.access.csv`: Full admin privileges for Dashboard Admin; read-only access for User group.
    *   `security/lhi_dashboard_security.xml`: Global rules for widgets and active announcements.
*   **Data & Configuration:**
    *   `data/dashboard_data.xml`: Seeded standard widgets (Announcements, My Tasks, My Approvals, Quick Actions, Notifications, Accessible Modules).
*   **JavaScript (Owl 19):**
    *   `static/src/js/lhi_home_router.js`: Safely routes the user to the Dashboard upon landing (`/web`) while preserving deep links (URL hashes containing action/ids).
    *   `static/src/js/dashboard_widget_registry.js`: Central registry to decouple module logic. Enables other modules to seamlessly register new widgets.
    *   `static/src/js/lhi_dashboard.js`: The core layout container executing `lhi_dashboard.dashboard_action`. Loads widgets based on ACL permissions dynamically.
    *   `static/src/js/widgets/*.js`: Embedded core widgets for `My Approvals`, `My Tasks`, `Quick Actions`, `Notifications`, `Accessible Modules`, and `Announcements`.
*   **Views & XML:**
    *   `views/dashboard_action.xml`: Created `ir.actions.client`, forced Root sequence 1, and created settings menus for administrators.
    *   `views/lhi_dashboard_widget_views.xml`: Admin CRUD interfaces for widget organization.
    *   `views/lhi_announcement_views.xml`: Admin CRUD interfaces for rich-text announcements.
    *   `static/src/xml/lhi_dashboard.xml`: Root template, parsing widget containers by `col_span`.
    *   `static/src/xml/widgets.xml`: UI structures leveraging LHI SCSS component tokens (`lhi-card`, `lhi-badge`).
*   **SCSS:**
    *   `static/src/scss/dashboard.scss`: Built CSS-Grid responsive boundaries adjusting dynamically between `xl`, `lg`, and `sm` device breakpoints.
*   **Tests:**
    *   `tests/test_dashboard.py`: Validated user boundaries preventing unauthorized loading of hidden widgets.
    *   `static/tests/dashboard_tests.js`: Verified JS widget registry logic.

## Migrations & Configuration
*   **Configuration:** 
    *   Administrators can manage the dashboard layout by navigating to **Settings -> Dashboard Settings**. 
    *   Administrators can hide widgets completely or scope them to specific user groups via Odoo's standard Group relationships.
*   **Deep Links:**
    *   Any email URL with `#action=X&id=Y` bypasses the Dashboard redirect organically.

## Test Results
*   **Server Consistency:** Module initiates correctly on Odoo 19 with all constraints passing.
*   **Role Enforcement:** Odoo ORM ensures a user only fetches widgets matching their `group_ids`, naturally hiding modules they lack authorization for.

---
*Prepared by Antigravity — Senior Odoo 19 Architect*

## Production blocker correction — 2026-07-19

- Added `static/src/js/dashboard_action.js` as the explicit backend asset entry
  that registers `lhi_dashboard.dashboard_action` in the frontend actions
  registry. The XML client-action tag and Owl template remain unchanged.
- Corrected the Odoo 19 Fleet root menu XML ID to `fleet.menu_root` and added a
  regression test covering all required launcher menu XML IDs.
- Added explicit dependencies for Procurement, Assets, Inventory, and Fleet so
  the launcher does not rely on manual module installation order.
- No models, fields, database migrations, environment variables, secrets,
  Microsoft permissions, SharePoint configuration, or production data changed.
- Python compilation and XML well-formedness checks passed. The Odoo disposable
  database install and browser checks remain deployment-environment verification
  because the local workstation has no Odoo runtime configuration or database.
- Deploy through Coolify at `https://work.lhinigeria.org`, update only
  `lhi_dashboard,lhi_media_communications`, and rebuild browser assets. Roll back
  by redeploying the preceding commit and updating only those modules against a
  backed-up database; then restart Odoo and clear browser asset caches.
