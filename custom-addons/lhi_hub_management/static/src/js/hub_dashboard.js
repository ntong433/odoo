/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class LhiHubDashboard extends Component {
    setup() {
        this.action = useService("action");
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            failed: false,
            cards: [],
            charts: [],
            warnings: [],
            currency: "",
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.failed = false;
        try {
            const data = await this.orm.call(
                "stock.warehouse",
                "get_lhi_hub_dashboard_data",
                []
            );
            this.state.cards = data.cards || [];
            this.state.charts = data.charts || [];
            this.state.warnings = data.warnings || [];
            this.state.currency = data.currency || "";
        } catch (error) {
            console.error("[LHI HUB] dashboard load failed", error);
            this.state.failed = true;
            this.notification.add(
                "The HUB overview could not be loaded. Operational lists remain available.",
                { type: "warning" }
            );
        } finally {
            this.state.loading = false;
        }
    }

    displayValue(item) {
        const value = Number(item.value || 0);
        const formatted = value.toLocaleString(undefined, {
            maximumFractionDigits: item.monetary ? 2 : 0,
        });
        return item.monetary ? `${this.state.currency} ${formatted}` : formatted;
    }

    openRecords(model, domain = []) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            name: "HUB Records",
            res_model: model,
            views: [[false, "list"], [false, "form"]],
            domain,
            target: "current",
        });
    }
}

LhiHubDashboard.template = "lhi_hub_management.HubDashboard";

registry
    .category("actions")
    .add("lhi_hub_management.hub_dashboard", LhiHubDashboard);
