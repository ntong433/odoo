/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { dashboardWidgetRegistry } from "./dashboard_widget_registry";

const actionRegistry = registry.category("actions");

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
        try {
            // Fetch authorized widgets configured by administrator
            const userWidgets = await this.orm.call(
                "lhi.dashboard.widget", 
                "get_user_widgets", 
                []
            );
            
            // Map the database config to actual registered JS components
            this.state.widgets = userWidgets.map(w => {
                const component = dashboardWidgetRegistry.get(w.registry_key);
                if (component) {
                    return { ...w, component };
                }
                console.warn(`Dashboard widget component '${w.registry_key}' not found in registry.`);
                return null;
            }).filter(Boolean);

        } catch (error) {
            console.error("Failed to load dashboard widgets", error);
        } finally {
            this.state.loading = false;
        }
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

// Register the dashboard as a client action
actionRegistry.add("lhi_dashboard.dashboard_action", LhiDashboard);
