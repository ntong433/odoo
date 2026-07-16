/** @odoo-module **/

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { dashboardWidgetRegistry } from "../dashboard_widget_registry";

export class NotificationsWidget extends Component {
    static template = "lhi_dashboard.NotificationsWidget";
    
    setup() {
        this.actionService = useService("action");
    }
    
    openInbox() {
        this.actionService.doAction("mail.action_discuss");
    }
}

dashboardWidgetRegistry.add("lhi_dashboard.notifications", NotificationsWidget);
