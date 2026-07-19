/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { dashboardWidgetRegistry } from "../dashboard_widget_registry";

export class MyApprovalsWidget extends Component {
    static template = "lhi_dashboard.MyApprovalsWidget";
    
    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = useState({
            count: 0,
            available: true,
            loading: true,
        });

        onWillStart(async () => {
            try {
                const result = await this.orm.call("lhi.dashboard.widget", "get_my_approval_summary", []);
                this.state.count = result.count;
                this.state.available = result.available;
            } catch (e) {
                console.error("Failed to load approvals", e);
                this.state.available = false;
            } finally {
                this.state.loading = false;
            }
        });
    }
    
    openApprovals() {
        if (!this.state.available) {
            return;
        }
        this.actionService.doAction("lhi_approval_matrix.action_lhi_my_pending_approvals");
    }
}

dashboardWidgetRegistry.add("lhi_dashboard.my_approvals", MyApprovalsWidget);
