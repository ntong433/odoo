/** @odoo-module **/
// ============================================================================
// LHI Notification Badge — Systray component
// Sprint 4 · lhi_web_shell · lhi_notification_badge.js
// ============================================================================

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class LhiNotificationBadge extends Component {
    static template = "lhi_web_shell.NotificationBadge";
    static props = {};

    setup() {
        // Future: hook up to mail.activity or notifications
    }
}

// Register it in the systray to appear in the top bar
registry.category("systray").add("lhi_web_shell.NotificationBadge", {
    Component: LhiNotificationBadge,
    sequence: 50,
});
