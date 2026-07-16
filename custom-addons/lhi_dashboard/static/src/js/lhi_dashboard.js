/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { dashboardWidgetRegistry } from "./dashboard_widget_registry";

const actionRegistry = registry.category("actions");

export class LhiDashboard extends Component {
    static template = "lhi_dashboard.Dashboard";
    static components = {}; // Will be populated with registry widgets dynamically

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.user = useService("user");
        
        this.state = useState({
            widgets: [],
            loading: true,
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
                    // Register locally for this instance to use dynamically
                    this.constructor.components[w.registry_key] = component;
                    return { ...w, componentLoaded: true };
                }
                console.warn(`Dashboard widget component '${w.registry_key}' not found in registry.`);
                return { ...w, componentLoaded: false };
            }).filter(w => w.componentLoaded);

        } catch (error) {
            console.error("Failed to load dashboard widgets", error);
        } finally {
            this.state.loading = false;
        }
    }
}

// Register the dashboard as a client action
actionRegistry.add("lhi_dashboard.dashboard_action", LhiDashboard);
