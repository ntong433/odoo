/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class LhiLeaveDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = useState({
            balances: [],
            staffOnLeave: [],
            isLoading: true,
        });

        onWillStart(async () => {
            await this.fetchData();
        });
    }

    async fetchData() {
        this.state.isLoading = true;
        
        try {
            // Fetch balances
            const balances = await this.orm.searchRead(
                "lhi.leave.cache",
                [],
                ["user_id", "annual_balance", "sick_balance", "is_stale"]
            );
            
            // Fetch staff on leave
            const staffOnLeave = await this.orm.searchRead(
                "lhi.leave.request.cache",
                [["status", "=", "approved"]],
                ["user_id", "leave_type", "start_date", "end_date"]
            );

            this.state.balances = balances;
            this.state.staffOnLeave = staffOnLeave;
        } catch (error) {
            console.error("Failed to fetch leave data", error);
        } finally {
            this.state.isLoading = false;
        }
    }
}

LhiLeaveDashboard.template = "lhi_leave_bridge.LeaveDashboard";
registry.category("actions").add("lhi_leave_bridge.dashboard", LhiLeaveDashboard);
