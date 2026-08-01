/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { dashboardWidgetRegistry } from "../dashboard_widget_registry";

export class AccessibleModulesWidget extends Component {
    static template = "lhi_dashboard.AccessibleModulesWidget";
    
    setup() {
        this.menuService = useService("menu");
        this.orm = useService("orm");
        this.state = useState({ apps: [], available: true });
        onWillStart(async () => {
            try {
                const result = await this.orm.call(
                    "lhi.dashboard.widget",
                    "get_accessible_apps",
                    []
                );
                if (result && !Array.isArray(result) && result.apps) {
                    this.state.apps = result.apps;
                    if (result.warnings && result.warnings.length > 0) {
                        for (const warning of result.warnings) {
                            this.env.services.notification.add(warning, { type: "warning", sticky: true, title: "Configuration Warning" });
                        }
                    }
                } else {
                    this.state.apps = result || [];
                }
            } catch (error) {
                console.error("[LHI Dashboard] My Apps is unavailable", error);
                this.state.apps = [];
                this.state.available = false;
            }
        });
    }

    async onAppClick(app) {
        if (app.menu_id) {
            try {
                await this.menuService.selectMenu(app.menu_id);
            } catch (error) {
                console.error(`[LHI Dashboard] Unable to open module ${app.name || app.xmlid || 'app'}`, error);
                this.env.services.notification.add(
                    "Unable to open this module. Please refresh and try again.", 
                    { type: "warning", sticky: false }
                );
            }
        } else {
            console.warn("[LHI Dashboard] App has no menu_id mapped", app);
        }
    }
}

dashboardWidgetRegistry.add("lhi_dashboard.accessible_modules", AccessibleModulesWidget);
