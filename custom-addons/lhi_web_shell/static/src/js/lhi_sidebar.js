/** @odoo-module **/
// ============================================================================
// LHI Sidebar — Shell Navigation Component
// Sprint 4 · lhi_web_shell · lhi_sidebar.js
// ============================================================================

import { Component, useState, onWillUnmount, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { resolveAppIcon } from "./icon_utils";

export class LhiSidebar extends Component {
    static template = "lhi_web_shell.Sidebar";
    static props = {};

    setup() {
        this.menuService = useService("menu");
        this.actionService = useService("action");
        
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
        const faFallback = { type: 'fa', class: 'fa fa-th-large' };

        if (!app.webIcon && !app.webIconData) return faFallback;

        // Base64-encoded image data from Odoo (must be a valid non-empty string)
        if (app.webIconData && typeof app.webIconData === 'string' && app.webIconData.length > 64) {
            return { type: 'image', src: resolveAppIcon(app.webIconData) };
        }

        if (app.webIcon) {
            // Module-relative static path: "module_name,path/to/icon.png"
            if (app.webIcon.includes(',')) {
                const [moduleName, iconPath] = app.webIcon.split(',');
                if (moduleName && iconPath) {
                    return { type: 'image', src: resolveAppIcon(`/${moduleName}/${iconPath}`) };
                }
            }

            // FontAwesome class reference
            if (app.webIcon.startsWith('fa-') || app.webIcon.startsWith('fa ')) {
                return { type: 'fa', class: `fa ${app.webIcon.replace(/^fa\s+/, '')}` };
            }
            
            // Raw paths or URLs
            if (app.webIcon.startsWith('/') || app.webIcon.startsWith('http')) {
                return { type: 'image', src: resolveAppIcon(app.webIcon) };
            }
        }

        return faFallback;
    }

    toggleCollapse() {
        this.state.collapsed = !this.state.collapsed;
        localStorage.setItem("lhi.sidebar.collapsed", this.state.collapsed ? "true" : "false");
        this._applySidebarState();
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
