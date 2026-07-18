/** @odoo-module **/

import { getAppIconProps } from "@lhi_web_shell/js/icon_utils";
import { openCurrentUserPreferences } from "@lhi_web_shell/js/preferences";

QUnit.module("LHI Web Shell Navigation", () => {
    QUnit.test("Preferences opens the authenticated user's existing record", async (assert) => {
        assert.expect(4);
        const returnedAction = { res_model: "res.users", view_mode: "form", target: "new" };
        const orm = {
            call(model, method) {
                assert.strictEqual(model, "res.users");
                assert.strictEqual(method, "action_get");
                return Promise.resolve(returnedAction);
            },
        };
        const actionService = {
            doAction(action) {
                assert.strictEqual(action.res_id, 42, "the current user ID is always set");
                assert.strictEqual(action, returnedAction, "the native action is executed");
            },
        };

        await openCurrentUserPreferences({ orm, actionService, userId: 42 });
    });

    QUnit.test("Preferences fails closed without a current-user record ID", async (assert) => {
        await assert.rejects(
            openCurrentUserPreferences({ orm: {}, actionService: {}, userId: false }),
            /authenticated user record/
        );
    });

    QUnit.test("stable XML IDs resolve the required sidebar icons", (assert) => {
        const mappings = {
            "lhi_funding_opportunity.menu_lhi_funding_root": "fa fa-filter",
            "lhi_purchase_request.menu_lhi_procurement_root": "fa fa-shopping-cart",
            "lhi_base.menu_lhi_operations": "fa fa-cogs",
            "lhi_asset_management.menu_lhi_asset": "fa fa-cubes",
        };
        for (const [xmlid, expectedClass] of Object.entries(mappings)) {
            assert.deepEqual(getAppIconProps({ xmlid }), { type: "fa", class: expectedClass });
        }
    });

    QUnit.test("unknown apps receive a supported fallback icon", (assert) => {
        assert.deepEqual(getAppIconProps({ xmlid: "example.unknown" }), {
            type: "fa",
            class: "fa fa-circle-o",
        });
    });
});
