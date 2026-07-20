/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class LhiDashboardAction extends Component {
    static template = "lhi_dashboard.Dashboard";
}

console.info(
    "[LHI Dashboard] registration file loaded"
);

registry.category("actions").add(
    "lhi_dashboard.dashboard_action",
    LhiDashboardAction
);

console.info(
    "[LHI Dashboard] registry contains action:",
    registry.category("actions").contains(
        "lhi_dashboard.dashboard_action"
    )
);
