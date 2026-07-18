/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { dashboardWidgetRegistry } from "../dashboard_widget_registry";

export class AccessibleModulesWidget extends Component {
    static template = "lhi_dashboard.AccessibleModulesWidget";
    
    setup() {
        this.menuService = useService("menu");
        this.orm = useService("orm");
        this.state = useState({ apps: [] });
        onWillStart(async () => {
            this.state.apps = await this.orm.call(
                "lhi.dashboard.widget",
                "get_accessible_apps",
                []
            );
        });
    }

    onAppClick(app) {
        this.menuService.selectMenu(app.menu_id);
    }
}

dashboardWidgetRegistry.add("lhi_dashboard.accessible_modules", AccessibleModulesWidget);
