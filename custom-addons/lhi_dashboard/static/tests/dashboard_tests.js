/** @odoo-module **/

import { getFixture, mount } from "@web/../tests/helpers/utils";
import { dashboardWidgetRegistry } from "@lhi_dashboard/js/dashboard_widget_registry";
import { makeTestEnv } from "@web/../tests/helpers/mock_env";
import { LhiDashboard } from "@lhi_dashboard/js/lhi_dashboard";

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
});
