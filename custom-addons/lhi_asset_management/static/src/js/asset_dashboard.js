/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export function normalizeAssetDashboardData(data) {
    const value = data && typeof data === "object" ? data : {};
    return {
        cards: Array.isArray(value.cards) ? value.cards : [],
        charts: Array.isArray(value.charts) ? value.charts : [],
        currency: typeof value.currency === "string" ? value.currency : "",
    };
}

export function formatAssetDashboardValue(item, currency, locale) {
    const parsed = Number(item?.value ?? 0);
    const value = Number.isFinite(parsed) ? parsed : 0;
    const formatted = value.toLocaleString(locale, {
        maximumFractionDigits: item?.monetary ? 2 : 0,
    });
    return item?.monetary ? `${currency} ${formatted}` : formatted;
}

export function buildAssetListAction(domain = []) {
    return {
        type: "ir.actions.act_window",
        name: "Asset Register",
        res_model: "lhi.asset",
        views: [[false, "list"], [false, "form"]],
        domain: Array.isArray(domain) ? domain : [],
        target: "current",
    };
}

export class LhiAssetDashboard extends Component {
    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            error: false,
            cards: [],
            charts: [],
            currency: "",
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.error = false;
        try {
            const result = await this.orm.call(
                "lhi.asset",
                "get_asset_dashboard_data",
                []
            );
            Object.assign(this.state, normalizeAssetDashboardData(result));
        } catch (error) {
            console.error("[LHI Asset Register] Dashboard load failed", error);
            this.state.error = true;
            this.notification.add(
                "The Asset Register overview could not be loaded. Your asset lists remain available.",
                { type: "warning" }
            );
        } finally {
            this.state.loading = false;
        }
    }

    displayValue(item) {
        return formatAssetDashboardValue(item, this.state.currency);
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

    openAssets(domain = []) {
        return this.action.doAction(buildAssetListAction(domain));
    }
}

LhiAssetDashboard.template = "lhi_asset_management.AssetDashboard";

registry
    .category("actions")
    .add("lhi_asset_management.asset_dashboard", LhiAssetDashboard);
