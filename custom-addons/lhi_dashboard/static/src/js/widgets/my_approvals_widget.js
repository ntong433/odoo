/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { dashboardWidgetRegistry } from "../dashboard_widget_registry";

export class MyApprovalsWidget extends Component {
    static template = "lhi_dashboard.MyApprovalsWidget";
    
    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = useState({
            count: 0,
            loading: true,
        });

        onWillStart(async () => {
            try {
                this.state.count = await this.orm.searchCount("lhi.approval.line", [
                    ['user_id', '=', user.userId],
                    ['status', '=', 'pending']
                ]);
            } catch (e) {
                console.error("Failed to load approvals", e);
            } finally {
                this.state.loading = false;
            }
        });
    }
    
    openApprovals() {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            name: 'My Pending Approvals',
            res_model: 'lhi.approval.line',
            view_mode: 'list,form',
            domain: [['user_id', '=', user.userId], ['status', '=', 'pending']],
            views: [[false, 'list'], [false, 'form']],
        });
    }
}

dashboardWidgetRegistry.add("lhi_dashboard.my_approvals", MyApprovalsWidget);
