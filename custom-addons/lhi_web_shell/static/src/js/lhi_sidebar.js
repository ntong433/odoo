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
        // Default fallback: FontAwesome cube
        const faFallback = { type: 'fa', class: 'fa fa-th-large' };

        if (!app.webIcon && !app.webIconData) return faFallback;

        // Base64-encoded image data from Odoo (must be a valid non-empty string)
        if (app.webIconData && typeof app.webIconData === 'string' && app.webIconData.length > 64) {
            return { type: 'image', src: `data:image/png;base64,${app.webIconData}` };
        }

        if (app.webIcon) {
            // Module-relative static path: "module_name,path/to/icon.png"
            if (app.webIcon.includes(',')) {
                const [moduleName, iconPath] = app.webIcon.split(',');
                if (moduleName && iconPath) {
                    return { type: 'image', src: `/${moduleName}/${iconPath}` };
                }
            }

            // FontAwesome class reference
            if (app.webIcon.startsWith('fa-') || app.webIcon.startsWith('fa ')) {
                return { type: 'fa', class: `fa ${app.webIcon.replace(/^fa\s+/, '')}` };
            }
        }

        return faFallback;
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
