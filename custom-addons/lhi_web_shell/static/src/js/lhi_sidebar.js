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
        this._appsFetchPromise = null;
        
        const savedCollapsed = localStorage.getItem("lhi.sidebar.collapsed") === "true";
        this.state = useState({
            collapsed: savedCollapsed,
            activeAppId: this.menuService.getCurrentApp()?.id || null,
            apps: [],
            isLoading: false,
            loadError: false,
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

    _normalizeAccessibleApps(rawApps) {
        const normalizedApps = [];
        const usedKeys = new Set();

        for (const app of rawApps || []) {
            if (!app || typeof app !== "object") {
                console.warn(
                    "[LHI Sidebar] Ignoring invalid application entry",
                    app
                );
                continue;
            }

            console.debug("[LHI Sidebar] raw application", {
                id: app.id,
                xmlid: app.xmlid,
                actionID: app.actionID,
                menu_id: app.menu_id,
                menuID: app.menuID,
                name: app.name,
            });

            const sourceKey =
                app.xmlid ||
                app.key ||
                app.id ||
                app.menu_id ||
                app.menuID ||
                app.actionID;

            if (
                sourceKey === undefined ||
                sourceKey === null ||
                sourceKey === ""
            ) {
                console.warn(
                    "[LHI Sidebar] Ignoring application without a stable key",
                    {
                        name: app.name,
                        id: app.id,
                        xmlid: app.xmlid,
                        menu_id: app.menu_id,
                        menuID: app.menuID,
                        actionID: app.actionID,
                    }
                );
                continue;
            }

            const stableKey = `lhi_app_${String(sourceKey)}`;

            if (usedKeys.has(stableKey)) {
                console.warn(
                    "[LHI Sidebar] Ignoring duplicate application",
                    {
                        stableKey,
                        name: app.name,
                    }
                );
                continue;
            }

            usedKeys.add(stableKey);

            const resolvedId = app.id || app.key || String(app.menu_id || app.xmlid || sourceKey);

            normalizedApps.push({
                ...app,
                id: resolvedId,
                _lhiSidebarKey: stableKey,
            });
        }

        return normalizedApps;
    }

    async _fetchAccessibleApps() {
        if (this._appsFetchPromise) {
            return this._appsFetchPromise;
        }

        this._appsFetchPromise = this._loadAccessibleApps();

        try {
            return await this._appsFetchPromise;
        } finally {
            this._appsFetchPromise = null;
        }
    }

    async _loadAccessibleApps() {
        this.state.isLoading = true;
        this.state.loadError = false;

        try {
            const result = await this.orm.call("lhi.dashboard.widget", "get_accessible_apps", []);
            const rawApps = (result && result.apps) ? result.apps : [];
            this.state.apps = this._normalizeAccessibleApps(rawApps);
        } catch (error) {
            console.error(
                "[LHI Sidebar] Failed to load accessible applications",
                {
                    message: error?.message,
                    name: error?.name,
                }
            );
            this.state.apps = [];
            this.state.loadError = true;
        } finally {
            this.state.isLoading = false;
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
