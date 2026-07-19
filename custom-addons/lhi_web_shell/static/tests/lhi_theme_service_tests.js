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
        document.documentElement.removeAttribute("data-lhi-theme");
        document.documentElement.removeAttribute("data-bs-theme");
    });

    QUnit.module("Theme Service");

    QUnit.test("Service initializes with system theme by default", async (assert) => {
        const env = await makeTestEnv();
        const service = lhiThemeService(env);
        
        assert.strictEqual(service.theme, "system", "Default theme should be system");
        assert.strictEqual(
            document.documentElement.getAttribute("data-lhi-theme"),
            window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light",
            "Resolved theme attribute should match system preference"
        );
    });

    QUnit.test("Service toggles theme and persists to localStorage", async (assert) => {
        const env = await makeTestEnv();
        const service = lhiThemeService(env);
        
        // Starts at system, toggles to light
        service.toggle();
        assert.strictEqual(service.theme, "light", "Theme should toggle to light");
        assert.strictEqual(service.isDark, false, "isDark should be false");
        assert.strictEqual(document.documentElement.getAttribute("data-lhi-theme"), "light", "data-lhi-theme should be light");
        assert.strictEqual(localStorage.getItem("lhi_theme"), "light", "localStorage should persist light theme");
        
        // Toggles to dark
        service.toggle();
        assert.strictEqual(service.theme, "dark", "Theme should toggle to dark");
        assert.strictEqual(service.isDark, true, "isDark should be true");
        assert.strictEqual(document.documentElement.getAttribute("data-lhi-theme"), "dark", "data-lhi-theme should be dark");
        assert.strictEqual(localStorage.getItem("lhi_theme"), "dark", "localStorage should persist dark theme");

        // Toggles to system
        service.toggle();
        assert.strictEqual(service.theme, "system", "Theme should toggle to system");
        assert.strictEqual(localStorage.getItem("lhi_theme"), "system", "localStorage should persist system theme");
    });
});
