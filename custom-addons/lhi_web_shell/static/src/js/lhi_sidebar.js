/** @odoo-module **/
// ============================================================================
// LHI Sidebar — Shell Navigation Component
// Sprint 4 · lhi_web_shell · lhi_sidebar.js
// ============================================================================

import { Component, useState, onWillUnmount, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { getAppIconProps } from "./icon_utils";
import { openCurrentUserPreferences } from "./preferences";

export class LhiSidebar extends Component {
    static template = "lhi_web_shell.Sidebar";
    static props = {};

    setup() {
        this.menuService = useService("menu");
        this.actionService = useService("action");
        this.orm = useService("orm");
        
        const savedCollapsed = localStorage.getItem("lhi.sidebar.collapsed") === "true";
        this.state = useState({
            collapsed: savedCollapsed,
            activeAppId: this.menuService.getCurrentApp()?.id || null,
        });

        const updateActiveApp = () => {
            const currentApp = this.menuService.getCurrentApp();
            if (currentApp) {
                this.state.activeAppId = currentApp.id;
            }
        };

        // Listen for route changes to update active app
        this.env.bus.addEventListener("ROUTE_CHANGE", updateActiveApp);
        
        onMounted(() => {
            this._applySidebarState();
        });

        onWillUnmount(() => {
            this.env.bus.removeEventListener("ROUTE_CHANGE", updateActiveApp);
        });
    }

    _applySidebarState() {
        requestAnimationFrame(() => {
            const webClient = document.querySelector(".o_web_client");
            if (webClient) {
                if (this.state.collapsed) {
                    webClient.classList.add("lhi-sidebar-collapsed");
                } else {
                    webClient.classList.remove("lhi-sidebar-collapsed");
                }
            }
        });
    }

    get apps() {
        const EXCLUDED_SIDEBAR_ROOTS = new Set([
            "lhi_dashboard.menu_lhi_dashboard_root",
            "lhi_base.menu_lhi_root",
            "lhi_integration.menu_lhi_erp_root"
        ]);
        return this.menuService.getApps().filter(
            (app) => !EXCLUDED_SIDEBAR_ROOTS.has(app.xmlid)
        );
    }

    getIconProps(app) {
        return getAppIconProps(app);
    }

    toggleCollapse() {
        this.state.collapsed = !this.state.collapsed;
        localStorage.setItem("lhi.sidebar.collapsed", this.state.collapsed ? "true" : "false");
        this._applySidebarState();
    }

    async onPreferencesClick() {
        await openCurrentUserPreferences({
            orm: this.orm,
            actionService: this.actionService,
            userId: user.userId,
        });
    }

    onAppClick(app) {
        if (app.id === 'dashboard') {
            this.state.activeAppId = 'dashboard';
            // Trigger Odoo's action manager to go to home or dashboard action.
            this.actionService.doAction("lhi_dashboard.action_lhi_dashboard");
            return;
        }

        this.state.activeAppId = app.id;
        this.menuService.selectMenu(app);
        
        // Handle mobile sidebar auto-close
        const webClient = document.querySelector(".o_web_client");
        if (webClient && window.innerWidth <= 992) {
            webClient.classList.remove("lhi-sidebar-open");
        }
    }
}

// Patch WebClient to include our Sidebar component
import { WebClient } from "@web/webclient/webclient";

Object.assign(WebClient.components, { LhiSidebar });
