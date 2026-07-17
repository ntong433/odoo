/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { dashboardWidgetRegistry } from "../dashboard_widget_registry";

export class QuickActionsWidget extends Component {
    static template = "lhi_dashboard.QuickActionsWidget";
    
    setup() {
        this.actionService = useService("action");
        this.orm = useService("orm");
        
        this.state = useState({
            actions: [],
            loading: true,
        });
        
        onWillStart(async () => {
            try {
                this.state.actions = await this.orm.call("lhi.dashboard.widget", "get_quick_actions", []);
            } catch (e) {
                console.error("Failed to load quick actions", e);
                this.state.actions = [];
            } finally {
                this.state.loading = false;
            }
        });
    }
    
    executeAction(action) {
        this.actionService.doAction({
            type: action.action_type,
            name: action.name,
            res_model: action.res_model,
            view_mode: action.view_mode,
            views: [[false, action.view_mode]],
            target: action.target,
        });
    }
}

dashboardWidgetRegistry.add("lhi_dashboard.quick_actions", QuickActionsWidget);
