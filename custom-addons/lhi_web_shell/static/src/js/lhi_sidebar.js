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
            apps: [],
        });

        const updateActiveApp = () => {
            const currentApp = this.menuService.getCurrentApp();
            if (currentApp) {
                this.state.activeAppId = currentApp.id;
            }
        };

        this.env.bus.addEventListener("ROUTE_CHANGE", updateActiveApp);
        
        onMounted(async () => {
            this._applySidebarState();
            await this._fetchAccessibleApps();
        });

        onWillUnmount(() => {
            this.env.bus.removeEventListener("ROUTE_CHANGE", updateActiveApp);
        });
    }

    async _fetchAccessibleApps() {
        try {
            const result = await this.orm.call("lhi.dashboard.widget", "get_accessible_apps", []);
            if (result && result.apps) {
                // The backend returns an array of objects: {key, name, menu_id, xmlid, icon_url}
                this.state.apps = result.apps;
            }
        } catch (e) {
            console.error("LHI Sidebar could not fetch accessible apps.", e);
        }
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
        return this.state.apps;
    }

    get generalApps() {
        return this.state.apps.filter((app) => app.key === "memos");
    }

    get businessApps() {
        return this.state.apps.filter((app) => app.key !== "memos");
    }

    getIconProps(app) {
        // Fallback to getting icon from the xmlid mapping
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

    _findFirstActionableMenu(menu) {
        if (!menu) {
            return null;
        }

        if (menu.actionID) {
            return menu;
        }

        for (const childId of menu.children || []) {
            const child = this.menuService.getMenu(childId);
            const target = this._findFirstActionableMenu(child);

            if (target) {
                return target;
            }
        }

        return null;
    }

    async onAppClick(app) {
        if (app.id === "dashboard" || app.key === "dashboard") {
            this.state.activeAppId = "dashboard";

            await this.actionService.doAction(
                "lhi_dashboard.action_lhi_dashboard",
                {
                    clearBreadcrumbs: true,
                }
            );

            return;
        }

        if (!app.menu_id) {
            console.error(
                "LHI Sidebar entry has no menu ID.",
                app
            );
            return;
        }

        const configuredMenu = this.menuService.getMenu(app.menu_id);

        if (!configuredMenu) {
            console.error(
                "LHI Sidebar menu is unavailable to the current user.",
                app.menu_id
            );
            return;
        }

        const targetMenu =
            this._findFirstActionableMenu(configuredMenu);

        if (!targetMenu) {
            console.error(
                "LHI Sidebar menu has no actionable visible child.",
                app.menu_id
            );
            return;
        }

        this.state.activeAppId =
            configuredMenu.appID ||
            targetMenu.appID ||
            app.menu_id;

        await this.menuService.selectMenu(targetMenu);

        const webClient =
            document.querySelector(".o_web_client");

        if (webClient && window.innerWidth <= 992) {
            webClient.classList.remove(
                "lhi-sidebar-open"
            );
        }
    }
}

// Patch WebClient to include our Sidebar component
import { WebClient } from "@web/webclient/webclient";

Object.assign(WebClient.components, { LhiSidebar });
