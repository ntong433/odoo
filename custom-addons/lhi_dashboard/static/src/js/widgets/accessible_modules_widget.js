/** @odoo-module **/

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { dashboardWidgetRegistry } from "../dashboard_widget_registry";

export class AccessibleModulesWidget extends Component {
    static template = "lhi_dashboard.AccessibleModulesWidget";
    
    setup() {
        this.menuService = useService("menu");
    }

    get apps() {
        return this.menuService.getApps();
    }

    onAppClick(app) {
        this.menuService.selectMenu(app);
    }
}

dashboardWidgetRegistry.add("lhi_dashboard.accessible_modules", AccessibleModulesWidget);
