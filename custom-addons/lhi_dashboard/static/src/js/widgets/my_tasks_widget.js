/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { dashboardWidgetRegistry } from "../dashboard_widget_registry";

export class MyTasksWidget extends Component {
    static template = "lhi_dashboard.MyTasksWidget";
    
    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = useState({
            count: 0,
            loading: true,
        });

        onWillStart(async () => {
            try {
                this.state.count = await this.orm.searchCount("mail.activity", [
                    ['user_id', '=', user.userId]
                ]);
            } catch (e) {
                console.error("Failed to load tasks", e);
            } finally {
                this.state.loading = false;
            }
        });
    }
    
    openTasks() {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            name: 'My Activities / Tasks',
            res_model: 'mail.activity',
            view_mode: 'list,form',
            domain: [['user_id', '=', user.userId]],
            views: [[false, 'list'], [false, 'form']],
        });
    }
}

dashboardWidgetRegistry.add("lhi_dashboard.my_tasks", MyTasksWidget);
