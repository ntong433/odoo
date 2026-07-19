/** @odoo-module **/

import { registry } from "@web/core/registry";

import { LhiDashboard } from "./lhi_dashboard";

export const DASHBOARD_ACTION_TAG = "lhi_dashboard.dashboard_action";

console.info("[LHI Dashboard] registering lhi_dashboard.dashboard_action");

// This key must exactly match the tag on action_lhi_dashboard.
registry.category("actions").add(
    "lhi_dashboard.dashboard_action",
    LhiDashboard
);
