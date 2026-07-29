import { describe, expect, test } from "@odoo/hoot";
import {
    buildHubRecordAction,
    formatHubDashboardValue,
    normalizeHubDashboardData,
} from "@lhi_hub_management/js/hub_dashboard";

describe("LHI HUB dashboard helpers", () => {
    test("keeps independent source warnings while normalizing data", () => {
        expect(
            normalizeHubDashboardData({
                cards: [{ key: "hubs", value: 1 }],
                charts: null,
                warnings: ["Lease metrics are unavailable."],
                currency: "NGN",
            })
        ).toEqual({
            cards: [{ key: "hubs", value: 1 }],
            charts: [],
            warnings: ["Lease metrics are unavailable."],
            currency: "NGN",
        });
        expect(normalizeHubDashboardData(undefined).warnings).toEqual([]);
    });

    test("formats permission-aware card values safely", () => {
        expect(
            formatHubDashboardValue(
                { value: 2500, monetary: true },
                "NGN",
                "en-US"
            )
        ).toBe("NGN 2,500");
        expect(
            formatHubDashboardValue(
                { value: Number.NaN, monetary: false },
                "NGN",
                "en-US"
            )
        ).toBe("0");
    });

    test("validates HUB drill-down actions", () => {
        const domain = [["state", "=", "quantity_review"]];
        expect(buildHubRecordAction("lhi.hub.stock.request", domain)).toEqual({
            type: "ir.actions.act_window",
            name: "HUB Records",
            res_model: "lhi.hub.stock.request",
            views: [[false, "list"], [false, "form"]],
            domain,
            target: "current",
        });
        expect(buildHubRecordAction("stock.quant", "invalid").domain).toEqual([]);
        expect(() => buildHubRecordAction("", [])).toThrow(
            "A HUB dashboard drill-down requires a model."
        );
    });
});
