/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export function normalizeHubDashboardData(data) {
    const value = data && typeof data === "object" ? data : {};
    return {
        cards: Array.isArray(value.cards) ? value.cards : [],
        charts: Array.isArray(value.charts) ? value.charts : [],
        warnings: Array.isArray(value.warnings) ? value.warnings : [],
        currency: typeof value.currency === "string" ? value.currency : "",
    };
}

export function formatHubDashboardValue(item, currency, locale) {
    const parsed = Number(item?.value ?? 0);
    const value = Number.isFinite(parsed) ? parsed : 0;
    const formatted = value.toLocaleString(locale, {
        maximumFractionDigits: item?.monetary ? 2 : 0,
    });
    return item?.monetary ? `${currency} ${formatted}` : formatted;
}

export function buildHubRecordAction(model, domain = []) {
    if (typeof model !== "string" || !model.trim()) {
        throw new TypeError("A HUB dashboard drill-down requires a model.");
    }
    return {
        type: "ir.actions.act_window",
        name: "HUB Records",
        res_model: model,
        views: [[false, "list"], [false, "form"]],
        domain: Array.isArray(domain) ? domain : [],
        target: "current",
    };
}

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
            Object.assign(this.state, normalizeHubDashboardData(data));
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
        return formatHubDashboardValue(item, this.state.currency);
    }

    displaySegmentValue(value) {
        const number = Number(value ?? 0);
        return Number.isFinite(number)
            ? number.toLocaleString()
            : "0";
    }

    displayDecimalValue(value, digits = 2) {
        const number = Number(value ?? 0);
        return Number.isFinite(number)
            ? number.toFixed(digits)
            : Number(0).toFixed(digits);
    }

    openRecords(model, domain = []) {
        if (typeof model !== "string" || !model.trim()) {
            this.notification.add(
                "This dashboard item has no valid record action.",
                { type: "warning" }
            );
            return false;
        }
        return this.action.doAction(buildHubRecordAction(model, domain));
    }
}

LhiHubDashboard.template = "lhi_hub_management.HubDashboard";

registry
    .category("actions")
    .add("lhi_hub_management.hub_dashboard", LhiHubDashboard);
