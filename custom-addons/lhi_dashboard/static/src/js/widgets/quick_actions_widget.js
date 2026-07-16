/** @odoo-module **/

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { dashboardWidgetRegistry } from "../dashboard_widget_registry";

export class QuickActionsWidget extends Component {
    static template = "lhi_dashboard.QuickActionsWidget";
    
    setup() {
        this.actionService = useService("action");
    }
    
    createApproval() {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            name: 'New Approval Request',
            res_model: 'lhi.approval.request',
            view_mode: 'form',
            views: [[false, 'form']],
            target: 'new',
        });
    }
}

dashboardWidgetRegistry.add("lhi_dashboard.quick_actions", QuickActionsWidget);
