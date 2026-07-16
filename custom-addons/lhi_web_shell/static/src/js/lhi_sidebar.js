/** @odoo-module **/
// ============================================================================
// LHI Sidebar — Shell Navigation Component
// Sprint 4 · lhi_web_shell · lhi_sidebar.js
// ============================================================================

import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class LhiSidebar extends Component {
    static template = "lhi_web_shell.Sidebar";
    static props = {};

    setup() {
        this.menuService = useService("menu");
        this.actionService = useService("action");
        this.state = useState({
            collapsed: false,
        });
    }

    get apps() {
        return this.menuService.getApps();
    }

    get currentApp() {
        return this.menuService.getCurrentApp();
    }

    toggleCollapse() {
        this.state.collapsed = !this.state.collapsed;
        // Update root css variable for layout
        if (this.state.collapsed) {
            document.querySelector(".o_web_client").classList.add("lhi-sidebar-collapsed");
        } else {
            document.querySelector(".o_web_client").classList.remove("lhi-sidebar-collapsed");
        }
    }

    onAppClick(app) {
        this.menuService.selectMenu(app);
    }
}

// Patch WebClient to include our Sidebar component
import { WebClient } from "@web/webclient/webclient";
import { patch } from "@web/core/utils/patch";

patch(WebClient.components, {
    ...WebClient.components,
    LhiSidebar,
});
