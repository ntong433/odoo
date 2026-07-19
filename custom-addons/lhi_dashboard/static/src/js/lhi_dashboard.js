/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { dashboardWidgetRegistry } from "./dashboard_widget_registry";

export class LhiDashboard extends Component {
    static template = "lhi_dashboard.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.menuService = useService("menu");
        this.user = user;
        
        this.state = useState({
            widgets: [],
            loading: true,
            error: false,
            searchQuery: "",
            searchResults: [],
            showSearchResults: false,
            isSearching: false,
        });

        onWillStart(async () => {
            await this.loadWidgets();
        });
    }

    async loadWidgets() {
        const delays = [0, 500, 1500, 3000];
        let userWidgets = null;
        this.state.error = false;

        for (let i = 0; i < delays.length; i++) {
            try {
                if (delays[i] > 0) {
                    await new Promise(resolve => setTimeout(resolve, delays[i]));
                }
                userWidgets = await this.orm.call(
                    "lhi.dashboard.widget", 
                    "get_user_widgets", 
                    []
                );
                break; // success
            } catch (error) {
                const errorStr = String(error?.name || error?.message || error || "");
                if (errorStr.includes("ConnectionLostError") || errorStr.includes("Connection") || errorStr.includes("XMLHttp")) {
                    console.warn(`RPC connection lost. Retrying in ${delays[i+1] || 'none'}ms...`);
                    if (i === delays.length - 1) {
                        console.error("Dashboard widget load failed after max retries.", error);
                        this.state.error = true;
                    }
                } else {
                    console.error("Failed to load dashboard widgets", error);
                    this.state.error = true;
                    break;
                }
            }
        }
        
        if (userWidgets) {
            // Map the database config to actual registered JS components
            this.state.widgets = userWidgets.map(w => {
                const component = dashboardWidgetRegistry.get(w.registry_key);
                if (component) {
                    return { ...w, component };
                }
                console.warn(`Dashboard widget component '${w.registry_key}' not found in registry.`);
                return null;
            }).filter(Boolean);
        }

        this.state.loading = false;
    }

    onSearchFocus() {
        if (this.state.searchQuery.length > 0) {
            this.state.showSearchResults = true;
        }
    }

    onSearchBlur() {
        // Delay hiding to allow click events on results to fire
        setTimeout(() => {
            this.state.showSearchResults = false;
        }, 200);
    }

    onSearchInput(ev) {
        const query = ev.target.value.toLowerCase();
        this.state.searchQuery = query;
        
        if (query.length < 2) {
            this.state.searchResults = [];
            this.state.showSearchResults = false;
            return;
        }

        this.state.isSearching = true;
        this.state.showSearchResults = true;

        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }

        this.searchTimeout = setTimeout(async () => {
            // Search through apps
            const apps = this.menuService.getApps();
            
            const localResults = apps
                .filter(app => app.name.toLowerCase().includes(query))
                .slice(0, 5)
                .map(app => ({
                    id: `app_${app.id}`,
                    name: app.name,
                    description: "Application",
                    icon: "cube",
                    actionID: app.actionID,
                    appID: app.id,
                    category: "App"
                }));
                
            try {
                // Search globally
                const globalResults = await this.orm.call("lhi.dashboard.widget", "global_search", [query]);
                this.state.searchResults = [...localResults, ...globalResults];
            } catch (e) {
                console.error("Global search failed:", e);
                this.state.searchResults = localResults;
            }
                
            this.state.isSearching = false;
        }, 300);
    }

    onSearchSelect(result) {
        this.state.showSearchResults = false;
        this.state.searchQuery = "";
        if (result.appID) {
            this.menuService.selectMenu(result.appID);
        } else if (result.actionID) {
            this.actionService.doAction(result.actionID);
        } else if (result.res_model && result.res_id) {
            this.actionService.doAction({
                type: 'ir.actions.act_window',
                res_model: result.res_model,
                res_id: result.res_id,
                views: [[false, 'form']],
                target: 'current',
            });
        }
    }
}
