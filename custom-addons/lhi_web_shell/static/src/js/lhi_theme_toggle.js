/** @odoo-module **/
// ============================================================================
// LHI Theme Toggle — Systray component
// Sprint 4 · lhi_web_shell · lhi_theme_toggle.js
// ============================================================================

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class LhiThemeToggle extends Component {
    static template = "lhi_web_shell.ThemeToggle";
    static props = {};

    setup() {
        this.theme = useService("lhi_theme");
    }

    toggleTheme() {
        this.theme.toggle();
    }
}

// Register it in the systray to appear in the top bar
registry.category("systray").add("lhi_web_shell.ThemeToggle", {
    Component: LhiThemeToggle,
    sequence: 40,
});
