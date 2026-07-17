/** @odoo-module **/
// ============================================================================
// LHI Sidebar — Shell Navigation Component
// Sprint 4 · lhi_web_shell · lhi_sidebar.js
// ============================================================================

import { Component, useState, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class LhiSidebar extends Component {
    static template = "lhi_web_shell.Sidebar";
    static props = {};

    setup() {
        this.menuService = useService("menu");
        this.actionService = useService("action");
        
        this.state = useState({
            collapsed: false,
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
        
        onWillUnmount(() => {
            this.env.bus.removeEventListener("ROUTE_CHANGE", updateActiveApp);
        });
    }

    get apps() {
        return this.menuService.getApps();
    }

    getIconProps(app) {
        if (!app.webIcon) return { type: 'fa', class: 'fa fa-cube' };
        if (app.webIconData) return { type: 'base64', src: `data:image/png;base64,${app.webIconData}` };
        if (app.webIcon.includes(',')) {
            const parts = app.webIcon.split(',');
            return { type: 'image', src: `/${parts[0]}/${parts[1]}` };
        }
        if (app.webIcon.startsWith('fa')) return { type: 'fa', class: app.webIcon };
        return { type: 'fa', class: 'fa fa-cube' };
    }

    toggleCollapse() {
        this.state.collapsed = !this.state.collapsed;
        
        // Use requestAnimationFrame for smoother transition synchronization
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

    onAppClick(app) {
        if (app.id === 'dashboard') {
            this.state.activeAppId = 'dashboard';
            // Trigger Odoo's action manager to go to home or dashboard action.
            // If there's a real dashboard app, we'd navigate to it. 
            // For now we assume clicking dashboard triggers a reload or a specific action.
            window.location.href = "/web";
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
