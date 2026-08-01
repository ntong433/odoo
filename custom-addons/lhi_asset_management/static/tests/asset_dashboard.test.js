import { describe, expect, test } from "@odoo/hoot";
import {
    LhiAssetDashboard,
    buildAssetListAction,
    formatAssetDashboardValue,
    normalizeAssetDashboardData,
} from "@lhi_asset_management/js/asset_dashboard";

describe("LHI Asset Register dashboard helpers", () => {
    test("normalizes inaccessible or malformed dashboard sources", () => {
        expect(normalizeAssetDashboardData(null)).toEqual({
            cards: [],
            charts: [],
            currency: "",
        });
        expect(
            normalizeAssetDashboardData({
                cards: [{ key: "total", value: 2 }],
                charts: "not-an-array",
                currency: "NGN",
            })
        ).toEqual({
            cards: [{ key: "total", value: 2 }],
            charts: [],
            currency: "NGN",
        });
    });

    test("formats monetary values and safely handles invalid numbers", () => {
        expect(
            formatAssetDashboardValue(
                { value: 1234.5, monetary: true },
                "NGN",
                "en-US"
            )
        ).toBe("NGN 1,234.5");
        expect(
            formatAssetDashboardValue(
                { value: "invalid", monetary: false },
                "NGN",
                "en-US"
            )
        ).toBe("0");
    });

    test("builds a bounded Asset Register drill-down action", () => {
        const domain = [["state", "=", "available"]];
        expect(buildAssetListAction(domain)).toEqual({
            type: "ir.actions.act_window",
            name: "Asset Register",
            res_model: "lhi.asset",
            views: [[false, "list"], [false, "form"]],
            domain,
            target: "current",
        });
        expect(buildAssetListAction("invalid").domain).toEqual([]);
    });

    test("formats segment values safely for numbers, numeric strings, null, undefined and invalid values", () => {
        const dashboard = new LhiAssetDashboard();
        expect(dashboard.displaySegmentValue(1250)).toBe((1250).toLocaleString());
        expect(dashboard.displaySegmentValue("4500")).toBe((4500).toLocaleString());
        expect(dashboard.displaySegmentValue(null)).toBe("0");
        expect(dashboard.displaySegmentValue(undefined)).toBe("0");
        expect(dashboard.displaySegmentValue("invalid")).toBe("0");

        expect(dashboard.displayDecimalValue(12.3456)).toBe("12.35");
        expect(dashboard.displayDecimalValue("99.9")).toBe("99.90");
        expect(dashboard.displayDecimalValue(null)).toBe("0.00");
        expect(dashboard.displayDecimalValue("invalid")).toBe("0.00");
    });
});
