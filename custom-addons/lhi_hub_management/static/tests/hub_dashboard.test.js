import { describe, expect, test } from "@odoo/hoot";
import {
    LhiHubDashboard,
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

    test("formats HUB segment values safely for numbers, numeric strings, null, undefined and invalid values", () => {
        const dashboard = new LhiHubDashboard();
        expect(dashboard.displaySegmentValue(3500)).toBe((3500).toLocaleString());
        expect(dashboard.displaySegmentValue("7200")).toBe((7200).toLocaleString());
        expect(dashboard.displaySegmentValue(null)).toBe("0");
        expect(dashboard.displaySegmentValue(undefined)).toBe("0");
        expect(dashboard.displaySegmentValue("invalid")).toBe("0");

        expect(dashboard.displayDecimalValue(45.678)).toBe("45.68");
        expect(dashboard.displayDecimalValue("100")).toBe("100.00");
        expect(dashboard.displayDecimalValue(null)).toBe("0.00");
        expect(dashboard.displayDecimalValue("invalid")).toBe("0.00");
    });
});
