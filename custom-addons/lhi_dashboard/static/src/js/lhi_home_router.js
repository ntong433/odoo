/** @odoo-module **/

import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";

const actionRegistry = registry.category("actions");

/**
 * LHI Home Router
 * Ensures that if a user navigates to the root with no deep link,
 * they are routed to the dashboard.
 */
function lhiHomeAction(env, action) {
    // Check if there is already a deep link in the hash
    const hash = browser.location.hash;
    if (hash && hash !== "#" && hash.includes("action=")) {
        // Allow normal routing if there's a deep link
        return;
    }

    // No deep link, route to the dashboard action
    env.services.action.doAction("lhi_dashboard.action_dashboard", {
        clearBreadcrumbs: true,
    });
}

// Register a client action that can be used as a home fallback
actionRegistry.add("lhi_dashboard.home_router", lhiHomeAction);
