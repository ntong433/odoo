/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

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
            this.state.cards = result.cards || [];
            this.state.charts = result.charts || [];
            this.state.currency = result.currency || "";
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
        const value = Number(item.value || 0);
        if (item.monetary) {
            return `${this.state.currency} ${value.toLocaleString(undefined, {
                maximumFractionDigits: 2,
            })}`;
        }
        return value.toLocaleString();
    }

    openAssets(domain = []) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            name: "Asset Register",
            res_model: "lhi.asset",
            views: [[false, "list"], [false, "form"]],
            domain,
            target: "current",
        });
    }
}

LhiAssetDashboard.template = "lhi_asset_management.AssetDashboard";

registry
    .category("actions")
    .add("lhi_asset_management.asset_dashboard", LhiAssetDashboard);
