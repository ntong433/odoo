/** @odoo-module **/

import { getAppIconProps } from "@lhi_web_shell/js/icon_utils";
import { openCurrentUserPreferences } from "@lhi_web_shell/js/preferences";
import { LhiSidebar } from "@lhi_web_shell/js/lhi_sidebar";

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

    QUnit.test("Sidebar navigation: child menu with action (MEAL)", async (assert) => {
        let selectedMenu = null;
        let actionTarget = null;

        const sidebar = Object.create(LhiSidebar.prototype);
        sidebar.state = { activeAppId: null };
        sidebar.menuService = {
            getMenu(id) {
                if (id === 45) {
                    return { id: 45, actionID: 501, appID: 40, name: "MEAL Initiatives" };
                }
                return null;
            },
            selectMenu(menu) {
                selectedMenu = menu;
                return Promise.resolve();
            },
        };
        sidebar.actionService = {
            doAction(action) {
                actionTarget = action;
                return Promise.resolve();
            },
        };

        const app = { menu_id: 45, xmlid: "lhi_meal.menu_lhi_meal_initiative" };
        await sidebar.onAppClick(app);

        assert.strictEqual(selectedMenu?.id, 45, "Selects configured child menu via menuService");
        assert.strictEqual(actionTarget, null, "No menu XML ID is passed to actionService.doAction()");
        assert.strictEqual(sidebar.state.activeAppId, 40, "Updates activeAppId to appID");
    });

    QUnit.test("Sidebar navigation: root menu with its own action", async (assert) => {
        let selectedMenu = null;
        const sidebar = Object.create(LhiSidebar.prototype);
        sidebar.state = { activeAppId: null };
        sidebar.menuService = {
            getMenu(id) {
                return id === 10 ? { id: 10, actionID: 101, appID: 10, name: "Media" } : null;
            },
            selectMenu(menu) {
                selectedMenu = menu;
                return Promise.resolve();
            },
        };
        sidebar.actionService = { doAction: () => Promise.resolve() };

        await sidebar.onAppClick({ menu_id: 10, xmlid: "lhi_media_communications.menu_lhi_media_root" });
        assert.strictEqual(selectedMenu?.id, 10);
    });

    QUnit.test("Sidebar navigation: root menu without action resolves first actionable child", async (assert) => {
        let selectedMenu = null;
        const menus = {
            20: { id: 20, actionID: null, children: [21], appID: 20 },
            21: { id: 21, actionID: 201, children: [], appID: 20 },
        };
        const sidebar = Object.create(LhiSidebar.prototype);
        sidebar.state = { activeAppId: null };
        sidebar.menuService = {
            getMenu(id) { return menus[id] || null; },
            selectMenu(menu) { selectedMenu = menu; return Promise.resolve(); },
        };
        sidebar.actionService = { doAction: () => Promise.resolve() };

        await sidebar.onAppClick({ menu_id: 20, xmlid: "lhi_base.menu_lhi_operations" });
        assert.strictEqual(selectedMenu?.id, 21, "Resolves and selects first actionable child");
        assert.strictEqual(sidebar.state.activeAppId, 20, "Sets activeAppId to root appID");
    });

    QUnit.test("Sidebar navigation: unavailable menu ID fails gracefully", async (assert) => {
        let selectedMenu = null;
        let actionTarget = null;
        const sidebar = Object.create(LhiSidebar.prototype);
        sidebar.state = { activeAppId: null };
        sidebar.menuService = {
            getMenu() { return null; },
            selectMenu(menu) { selectedMenu = menu; return Promise.resolve(); },
        };
        sidebar.actionService = { doAction(action) { actionTarget = action; return Promise.resolve(); } };

        await sidebar.onAppClick({ menu_id: 999, xmlid: "unknown.menu" });
        assert.strictEqual(selectedMenu, null);
        assert.strictEqual(actionTarget, null);
    });

    QUnit.test("Sidebar navigation: menu with no actionable descendants fails gracefully", async (assert) => {
        let selectedMenu = null;
        const menus = {
            30: { id: 30, actionID: null, children: [31] },
            31: { id: 31, actionID: null, children: [] },
        };
        const sidebar = Object.create(LhiSidebar.prototype);
        sidebar.state = { activeAppId: null };
        sidebar.menuService = {
            getMenu(id) { return menus[id] || null; },
            selectMenu(menu) { selectedMenu = menu; return Promise.resolve(); },
        };
        sidebar.actionService = { doAction: () => Promise.resolve() };

        await sidebar.onAppClick({ menu_id: 30, xmlid: "empty.menu" });
        assert.strictEqual(selectedMenu, null);
    });

    QUnit.test("Sidebar navigation: dashboard client action remains functional", async (assert) => {
        let actionTarget = null;
        let selectedMenu = null;
        const sidebar = Object.create(LhiSidebar.prototype);
        sidebar.state = { activeAppId: null };
        sidebar.menuService = {
            selectMenu(menu) { selectedMenu = menu; return Promise.resolve(); },
        };
        sidebar.actionService = {
            doAction(action, options) {
                actionTarget = { action, options };
                return Promise.resolve();
            },
        };

        await sidebar.onAppClick({ id: "dashboard", key: "dashboard" });
        assert.strictEqual(actionTarget?.action, "lhi_dashboard.action_lhi_dashboard");
        assert.strictEqual(actionTarget?.options?.clearBreadcrumbs, true);
        assert.strictEqual(selectedMenu, null, "Dashboard client action does not call selectMenu");
        assert.strictEqual(sidebar.state.activeAppId, "dashboard");
    });
});
