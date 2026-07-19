/** @odoo-module **/
// ============================================================================
// LHI Theme Service — light / dark / system mode persistence
// Sprint 4 · lhi_web_shell · lhi_theme_service.js
// ============================================================================

import { registry }  from "@web/core/registry";
import { reactive }  from "@odoo/owl";

const LHI_THEME_KEY = "lhi_theme";
const DARK_VALUE    = "dark";
const LIGHT_VALUE   = "light";
const SYSTEM_VALUE  = "system";

/**
 * Apply the theme attributes to the HTML element.
 * @param {"dark"|"light"|"system"} theme
 */
function applyTheme(theme) {
    let resolvedTheme = theme;
    if (theme === SYSTEM_VALUE) {
        resolvedTheme = window.matchMedia("(prefers-color-scheme: dark)").matches ? DARK_VALUE : LIGHT_VALUE;
    }
    document.documentElement.setAttribute("data-lhi-theme", resolvedTheme);
    document.documentElement.setAttribute("data-bs-theme", resolvedTheme);
}

// Media listener to dynamically update theme when system preference changes
const systemMediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
systemMediaQuery.addEventListener("change", () => {
    const saved = localStorage.getItem(LHI_THEME_KEY) || SYSTEM_VALUE;
    if (saved === SYSTEM_VALUE) {
        applyTheme(SYSTEM_VALUE);
    }
});

/** Build and return the theme service instance. */
function lhiThemeService(env) {
    const saved = localStorage.getItem(LHI_THEME_KEY) || SYSTEM_VALUE;
    const state = reactive({ theme: saved });

    // Initial application of theme
    applyTheme(saved);

    return {
        /** @returns {"dark"|"light"|"system"} */
        get theme() {
            return state.theme;
        },

        /** @returns {boolean} */
        get isDark() {
            if (state.theme === SYSTEM_VALUE) {
                return window.matchMedia("(prefers-color-scheme: dark)").matches;
            }
            return state.theme === DARK_VALUE;
        },

        /** Toggle cycle: light -> dark -> system -> light */
        toggle() {
            let next;
            if (state.theme === LIGHT_VALUE) {
                next = DARK_VALUE;
            } else if (state.theme === DARK_VALUE) {
                next = SYSTEM_VALUE;
            } else {
                next = LIGHT_VALUE;
            }
            state.theme = next;
            localStorage.setItem(LHI_THEME_KEY, next);
            applyTheme(next);
        },

        /**
         * Set a specific theme.
         * @param {"dark"|"light"|"system"} theme
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
