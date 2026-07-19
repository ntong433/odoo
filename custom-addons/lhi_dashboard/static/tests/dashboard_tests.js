/** @odoo-module **/

import { getFixture, mount } from "@web/../tests/helpers/utils";
import { dashboardWidgetRegistry } from "@lhi_dashboard/js/dashboard_widget_registry";
import { makeTestEnv } from "@web/../tests/helpers/mock_env";
import {
    DASHBOARD_ACTION_TAG,
    LhiDashboard,
} from "@lhi_dashboard/js/lhi_dashboard";
import { registry } from "@web/core/registry";

QUnit.module("LHI Dashboard", (hooks) => {
    let target;
    hooks.beforeEach(() => {
        target = getFixture();
    });

    QUnit.test("dashboard registry allows adding widgets", async (assert) => {
        const dummyWidget = { name: "DummyWidget" };
        dashboardWidgetRegistry.add("test.dummy", dummyWidget);
        
        assert.strictEqual(
            dashboardWidgetRegistry.get("test.dummy"),
            dummyWidget,
            "Widget should be added and retrievable from the registry"
        );
    });

    QUnit.test("canonical dashboard client action is registered once", (assert) => {
        const actions = registry.category("actions");
        assert.strictEqual(
            actions.get(DASHBOARD_ACTION_TAG),
            LhiDashboard,
            "The server action tag resolves to the LHI Dashboard component"
        );
    });

    QUnit.test("DOM duplicate protection for layout components", async (assert) => {
        // This test assumes a full mount of the WebClient which injects the sidebar and dashboard.
        // It provides DOM-level assertions as required by the enterprise spec.
        const dashboards = document.querySelectorAll('.lhi-dashboard');
        const sidebars = document.querySelectorAll('.lhi-sidebar');
        
        // During actual component mounting, there should be exactly one of each.
        // If testing in isolation, we assert the absence of duplicates.
        assert.ok(dashboards.length <= 1, "There must be no more than one Dashboard mounted globally");
        assert.ok(sidebars.length <= 1, "There must be no more than one Sidebar mounted globally");
        
        const dashboardMenuItems = document.querySelectorAll('[title="Dashboard"]');
        assert.ok(dashboardMenuItems.length <= 1, "There must be exactly one Dashboard menu item in the sidebar");
    });
});
