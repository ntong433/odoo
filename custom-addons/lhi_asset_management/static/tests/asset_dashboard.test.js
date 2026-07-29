import { describe, expect, test } from "@odoo/hoot";
import {
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
});
