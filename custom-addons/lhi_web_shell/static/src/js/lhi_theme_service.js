/** @odoo-module **/
// ============================================================================
// LHI Theme Service — light / dark mode persistence
// Sprint 4 · lhi_web_shell · lhi_theme_service.js
//
// Registers an Odoo service that:
//   1. Reads the saved preference from localStorage
//   2. Applies data-theme="dark" (or removes it) on <html>
//   3. Exposes toggle() and isDark reactive state for Owl components
// ============================================================================

import { registry }  from "@web/core/registry";
import { reactive }  from "@odoo/owl";

const LHI_THEME_KEY = "lhi_theme";
const DARK_VALUE    = "dark";
const LIGHT_VALUE   = "light";

/**
 * Apply the theme to the DOM.
 * @param {"dark"|"light"} theme
 */
function applyTheme(theme) {
    if (theme === DARK_VALUE) {
        document.documentElement.setAttribute("data-theme", DARK_VALUE);
    } else {
        document.documentElement.removeAttribute("data-theme");
    }
}

/** Build and return the theme service instance. */
function lhiThemeService(env) {
    const saved  = localStorage.getItem(LHI_THEME_KEY) || LIGHT_VALUE;
    const state  = reactive({ theme: saved });

    applyTheme(saved);

    return {
        /** @returns {"dark"|"light"} */
        get theme() {
            return state.theme;
        },

        /** @returns {boolean} */
        get isDark() {
            return state.theme === DARK_VALUE;
        },

        /** Toggle between light and dark, persist to localStorage. */
        toggle() {
            const next = state.theme === DARK_VALUE ? LIGHT_VALUE : DARK_VALUE;
            state.theme = next;
            localStorage.setItem(LHI_THEME_KEY, next);
            applyTheme(next);
        },

        /**
         * Set a specific theme.
         * @param {"dark"|"light"} theme
         */
        setTheme(theme) {
            state.theme = theme;
            localStorage.setItem(LHI_THEME_KEY, theme);
            applyTheme(theme);
        },
    };
}

// Register in Odoo service registry under the lhi_ namespace
registry.category("services").add("lhi_theme", {
    start: lhiThemeService,
});

export { lhiThemeService };
