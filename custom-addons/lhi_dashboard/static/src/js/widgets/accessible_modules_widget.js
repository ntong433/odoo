/** @odoo-module **/

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { dashboardWidgetRegistry } from "../dashboard_widget_registry";
import { resolveAppIcon } from "@lhi_web_shell/js/icon_utils";

export class AccessibleModulesWidget extends Component {
    static template = "lhi_dashboard.AccessibleModulesWidget";
    
    setup() {
        this.menuService = useService("menu");
    }

    get apps() {
        return this.menuService.getApps();
    }

    getIconProps(app) {
        if (!app.webIcon && !app.webIconData) return { type: 'fa', class: 'fa fa-cube' };
        
        if (app.webIconData && typeof app.webIconData === 'string' && app.webIconData.length > 64) {
            return { type: 'image', src: resolveAppIcon(app.webIconData) };
        }
        
        if (app.webIcon) {
            if (app.webIcon.includes(',')) {
                const parts = app.webIcon.split(',');
                return { type: 'image', src: resolveAppIcon(`/${parts[0]}/${parts[1]}`) };
            }
            if (app.webIcon.startsWith('fa')) return { type: 'fa', class: app.webIcon };
            
            if (app.webIcon.startsWith('/') || app.webIcon.startsWith('http')) {
                return { type: 'image', src: resolveAppIcon(app.webIcon) };
            }
        }
        return { type: 'fa', class: 'fa fa-cube' };
    }

    onAppClick(app) {
        this.menuService.selectMenu(app);
    }
}

dashboardWidgetRegistry.add("lhi_dashboard.accessible_modules", AccessibleModulesWidget);
