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

    onAppClick(app) {
        this.menuService.selectMenu(app);
    }
}

dashboardWidgetRegistry.add("lhi_dashboard.accessible_modules", AccessibleModulesWidget);
