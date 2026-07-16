/** @odoo-module **/

import { getFixture, mount } from "@web/../tests/helpers/utils";
import { lhiThemeService } from "@lhi_web_shell/js/lhi_theme_service";
import { registry } from "@web/core/registry";
import { makeTestEnv } from "@web/../tests/helpers/mock_env";

QUnit.module("LHI Web Shell", (hooks) => {
    let target;
    let originalTheme;

    hooks.beforeEach(() => {
        target = getFixture();
        originalTheme = localStorage.getItem("lhi_theme");
        localStorage.removeItem("lhi_theme");
    });

    hooks.afterEach(() => {
        if (originalTheme) {
            localStorage.setItem("lhi_theme", originalTheme);
        } else {
            localStorage.removeItem("lhi_theme");
        }
        document.documentElement.removeAttribute("data-theme");
    });

    QUnit.module("Theme Service");

    QUnit.test("Service initializes with light theme by default", async (assert) => {
        const env = await makeTestEnv();
        const service = lhiThemeService(env);
        
        assert.strictEqual(service.theme, "light", "Default theme should be light");
        assert.strictEqual(service.isDark, false, "isDark should be false");
        assert.strictEqual(document.documentElement.getAttribute("data-theme"), null, "data-theme attribute should be null");
    });

    QUnit.test("Service toggles theme and persists to localStorage", async (assert) => {
        const env = await makeTestEnv();
        const service = lhiThemeService(env);
        
        service.toggle();
        
        assert.strictEqual(service.theme, "dark", "Theme should toggle to dark");
        assert.strictEqual(service.isDark, true, "isDark should be true");
        assert.strictEqual(document.documentElement.getAttribute("data-theme"), "dark", "data-theme attribute should be dark");
        assert.strictEqual(localStorage.getItem("lhi_theme"), "dark", "localStorage should persist dark theme");
        
        service.toggle();
        
        assert.strictEqual(service.theme, "light", "Theme should toggle back to light");
        assert.strictEqual(service.isDark, false, "isDark should be false");
        assert.strictEqual(document.documentElement.getAttribute("data-theme"), null, "data-theme attribute should be removed");
        assert.strictEqual(localStorage.getItem("lhi_theme"), "light", "localStorage should persist light theme");
    });
});
